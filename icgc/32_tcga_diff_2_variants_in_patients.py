#! /usr/bin/python
import subprocess
import time, re

from icgc_utils.common_queries import *
from icgc_utils.processes import *

tcga_icgc_table_correspondence = {
"ACC_somatic_mutations" :  "ACC_simple_somatic",
"ALL_somatic_mutations" :  "ALL_simple_somatic",
"BLCA_somatic_mutations": "BLCA_simple_somatic",
"BRCA_somatic_mutations": "BRCA_simple_somatic",
"CESC_somatic_mutations": "CESC_simple_somatic",
"CHOL_somatic_mutations": "CHOL_simple_somatic",
"COAD_somatic_mutations": "COCA_simple_somatic",
"DLBC_somatic_mutations": "DLBC_simple_somatic",
"ESCA_somatic_mutations": "ESAD_simple_somatic",
"GBM_somatic_mutations" :  "GBM_simple_somatic",
"HNSC_somatic_mutations": "HNSC_simple_somatic",
"KICH_somatic_mutations": "KICH_simple_somatic",
"KIRC_somatic_mutations": "KIRC_simple_somatic",
"KIRP_somatic_mutations": "KIRP_simple_somatic",
"LAML_somatic_mutations":  "AML_simple_somatic",
"LGG_somatic_mutations" :  "LGG_simple_somatic",
"LIHC_somatic_mutations": "LICA_simple_somatic",
"LUAD_somatic_mutations": "LUAD_simple_somatic",
"LUSC_somatic_mutations": "LUSC_simple_somatic",
"MESO_somatic_mutations": "MESO_simple_somatic",
"OV_somatic_mutations"  :   "OV_simple_somatic",
"PAAD_somatic_mutations": "PACA_simple_somatic",
"PCPG_somatic_mutations": "PCPG_simple_somatic",
"PRAD_somatic_mutations": "PRAD_simple_somatic",
"READ_somatic_mutations": "COCA_simple_somatic",
"SARC_somatic_mutations": "SARC_simple_somatic",
"SKCM_somatic_mutations": "MELA_simple_somatic",
"STAD_somatic_mutations": "GACA_simple_somatic",
"TGCT_somatic_mutations": "TGCT_simple_somatic",
"THCA_somatic_mutations": "THCA_simple_somatic",
"THYM_somatic_mutations": "THYM_simple_somatic",
"UCEC_somatic_mutations": "UCEC_simple_somatic",
"UCS_somatic_mutations" : "UTCA_simple_somatic",
"UVM_somatic_mutations" :  "UVM_simple_somatic"
}

variant_columns = ['icgc_mutation_id', 'chromosome','icgc_donor_id', 'icgc_specimen_id', 'icgc_sample_id',
                   'submitted_sample_id','control_genotype', 'tumor_genotype', 'total_read_count', 'mutant_allele_read_count']

# we'll take care of 'aa_mutation' and 'consequence_type will be handled separately
mutation_columns = ['icgc_mutation_id', 'start_position', 'end_position', 'mutation_type',
					'mutated_from_allele', 'mutated_to_allele', 'reference_genome_allele']

location_columns = ['position', 'gene_relative', 'transcript_relative']

################################################################
# stop_retained: A sequence variant where at least one base in the terminator codon is changed, but the terminator remains
consequence_vocab = ['stop_lost', 'synonymous', 'inframe_deletion', 'inframe_insertion', 'stop_gained',
                     '5_prime_UTR_premature_start_codon_gain',
                     'start_lost', 'frameshift', 'disruptive_inframe_deletion', 'stop_retained',
                     'exon_loss', 'disruptive_inframe_insertion', 'missense']

# location_vocab[1:4] is gene-relative
# location_vocab[1:4] is transcript-relative
location_vocab = ['intergenic_region', 'intragenic', 'upstream', 'downstream',
                  '5_prime_UTR', 'exon',  'coding_sequence', 'initiator_codon',
                  'splice_acceptor', 'splice_region', 'splice_donor',
                  'intron', '3_prime_UTR', ]

# this is set literal
pathogenic = {'stop_lost', 'inframe_deletion', 'inframe_insertion', 'stop_gained', '5_prime_UTR_premature_start_codon_gain',
                     'start_lost', 'frameshift', 'disruptive_inframe_deletion',
                     'exon_loss', 'disruptive_inframe_insertion', 'missense',
                     'splice_acceptor', 'splice_region', 'splice_donor', 'inframe'
             }


#########################################
def quotify(something):
	if not something:
		return ""
	if type(something)==str:
		return "\'"+something+"\'"
	else:
		return str(something)


#########################################
def check_location_stored(cursor, tcga_named_field):
	location_table = "locations_chrom_%s" % tcga_named_field['chromosome']
	qry = "select count(*) from %s where position=%s"%(location_table, tcga_named_field['start_position'])
	ret = search_db(cursor,qry)
	if ret and len(ret)>1:
		print "problem: non-unique location id"
		print qry
		print ret
		exit()
	return False if not ret else ret[0][0]


#########################################
def find_mutation_id(cursor, tcga_named_field):
	mutation_table = "mutations_chrom_%s" % tcga_named_field['chromosome']
	qry = "select icgc_mutation_id, pathogenic_estimate from icgc.%s where start_position=%s "%(mutation_table, tcga_named_field['start_position'])
	reference_allele = tcga_named_field['reference_allele']
	differing_allele = tcga_named_field['tumor_seq_allele1']
	if differing_allele == reference_allele: differing_allele = tcga_named_field['tumor_seq_allele2']
	if len(reference_allele)>200: reference_allele=reference_allele[:200]+"etc"
	if len(differing_allele)>200: differing_allele=differing_allele[:200]+"etc"
	qry += "and mutated_from_allele='%s' and mutated_to_allele='%s' "%(reference_allele,differing_allele)
	ret = search_db(cursor,qry)

	if not ret:
		print "problem: no return for"
		print qry
		exit() # brilliant idea in case of multithreading
	if len(ret)>1:
		print "problem: non-unique mutation id"
		print qry
		print ret
		exit()
	return False if not ret else ret[0]

#########################################
def construct_id(cursor, icgc_table, lock_alias):
	# construct donor id
	qry  = "select icgc_donor_id from icgc.%s as %s "  % (icgc_table, lock_alias)
	qry += "where icgc_donor_id like 'DOT_%' order by icgc_donor_id desc limit 1"
	ret = search_db(cursor,qry)
	ordinal = 1
	if ret:
		ordinal = int( ret[0][0].split("_")[-1].lstrip("0") ) + 1
	tumor_short = icgc_table.split("_")[0]
	return "DOT_%s_%05d"%(tumor_short,ordinal)

#########################################
id_resolution = {}

#########################################
def store_variant(cursor,  tcga_named_field, mutation_id, pathogenic_estimate, icgc_table):

	# thread parallelization goes over tcga tables - no guarantee there won't be race condition
	# for icgc tables
	# lock table
	lock_alias = "varslock"
	qry = "lock tables %s write, %s as %s read" % (icgc_table, icgc_table, lock_alias)
	search_db(cursor,qry)

	#have we stored this by any chance?
	qry  = "select submitted_sample_id from icgc.%s " % icgc_table
	qry += "where icgc_mutation_id='%s' " % mutation_id
	ret = search_db(cursor,qry)

	# we have not stored this one yet
	if ret and (tcga_named_field['tumor_sample_barcode'] in [r[0] for r in ret]):
		#print "variant found"
		pass
	else:
		tcga_participant_id = "-".join(tcga_named_field['tumor_sample_barcode'].split("-")[:3])
		if id_resolution.has_key(tcga_participant_id):
			new_donor_id = id_resolution[tcga_participant_id]
		else:
			new_donor_id = construct_id(cursor, icgc_table, lock_alias)
			id_resolution[tcga_participant_id] = new_donor_id

		# tcga could not agree in which column to place the cancer allele
		reference_allele = tcga_named_field['reference_allele']
		differing_allele = tcga_named_field['tumor_seq_allele1']
		if differing_allele == reference_allele: differing_allele = tcga_named_field['tumor_seq_allele2']
		if len(reference_allele)>200: reference_allele=reference_allele[:200]+"etc"
		if len(differing_allele)>200: differing_allele=differing_allele[:200]+"etc"

		# fill store hash
		store_fields = {
			'icgc_mutation_id': mutation_id,
			'chromosome': tcga_named_field['chromosome'],
			'icgc_donor_id': new_donor_id,
			'submitted_sample_id':tcga_named_field['tumor_sample_barcode'],
			'tumor_genotype': "{}/{}".format(reference_allele,differing_allele),
			'pathogenic_estimate': pathogenic_estimate,
			'reliability_estimate': 1,
		}
		# store
		store_without_checking(cursor, icgc_table, store_fields, verbose=False, database='icgc')


	# unlock
	qry = "unlock tables"
	search_db(cursor,qry)

	return



#########################################
def process_table(cursor, tcga_table, icgc_table, already_deposited_samples):

	standard_chromosomes = [str(i) for i in range(23)] +['X','Y']

	# make a workdir and move there
	tumor_short = tcga_table.split("_")[0]
	no_rows = search_db(cursor,"select count(*) from tcga.%s"% tcga_table)[0][0]

	column_names = get_column_names(cursor,'tcga',tcga_table)
	qry  = "select * from tcga.%s " % tcga_table
	ct = 0
	time0 = time.time()
	for row in search_db(cursor,qry):
		ct += 1
		if (ct%10000==0):
			print "%30s   %6d lines out of %6d  (%d%%)  %d min" % \
			      (tcga_table, ct, no_rows, float(ct)/no_rows*100, float(time.time()-time0)/60)
		named_field = dict(zip(column_names,row))
		if named_field['tumor_sample_barcode'] in already_deposited_samples: continue
		if not  named_field['chromosome'] in standard_chromosomes: continue
		mutation_id, pathogenic_estimate = find_mutation_id(cursor, named_field)
		location_stored = check_location_stored(cursor, named_field)
		if not mutation_id or not location_stored:
			print "mutation id:", mutation_id
			print "location stored:", location_stored
			exit()
		# all clear - store
		store_variant(cursor, named_field, mutation_id, pathogenic_estimate, icgc_table)



#########################################
def add_tcga_diff(tcga_tables, other_args):

	db     = connect_to_mysql()
	cursor = db.cursor()
	for tcga_table in tcga_tables:

		icgc_table =  tcga_icgc_table_correspondence[tcga_table]

		# where in the icgc classification does this symbol belong?
		time0 = time.time()
		print
		print "===================="
		print "processing tcga table ", tcga_table, os.getpid()
		print "will be stored in ", icgc_table

		#tcga samples in tcga_table
		qry = "select distinct(tumor_sample_barcode) from tcga.%s" % tcga_table
		tcga_tumor_sample_ids = [ret[0] for ret in search_db(cursor,qry)]

		#tcga samples already deposited in icgc
		# NOTE: it looks like in TCGA database the only id type different from TCGA*
		# can be TARGET * (and that one in ALL set only)
		qry  = "select distinct(submitted_sample_id) from icgc.%s " % icgc_table
		qry += "where (submitted_sample_id like 'tcga%' or submitted_sample_id like 'target%')"
		qry += "and icgc_donor_id not like 'DOT%' "  # these are new id's we are creating here
		ret = search_db(cursor,qry)
		icgc_tumor_sample_ids = [r[0] for r in ret] if ret else []

		#tcga samples already deposited in icgc
		already_deposited_samples = list(set(icgc_tumor_sample_ids).difference(set(tcga_tumor_sample_ids)))
		samples_not_deposited     = list(set(tcga_tumor_sample_ids).difference(set(icgc_tumor_sample_ids)))

		# I am taking a leap of faith here, and I believe that the deposited data is
		# really identical to what we have in tcga
		print "not deposited:", len(samples_not_deposited)
		print "already deposited:", len(already_deposited_samples)

		process_table(cursor, tcga_table, icgc_table, already_deposited_samples)
		print "\t overall time for %s: %.3f mins; pid: %d" % (tcga_table, float(time.time()-time0)/60, os.getpid())

	cursor.close()
	db.close()

	return


#########################################
#########################################
def main():

	print "note there is a bug around the line 157: id_resolution"
	print "it should be checked whether the saem _donor_ already exists in the database"
	print "we have only checked whether the _sample_ from the same donor already exists"
	exit()

	# divide by cancer types, because I have duplicates within each cancer type
	# that I'll resolve as I go, but I do not want the threads competing)
	db     = connect_to_mysql()
	cursor = db.cursor()

	qry  = "select table_name from information_schema.tables "
	qry += "where table_schema='tcga' and table_name like '%_somatic_mutations'"
	tcga_tables = [field[0] for field in search_db(cursor,qry)]

	number_of_chunks = 8 # myISAM does not deadlock
	parallelize(number_of_chunks, add_tcga_diff, tcga_tables, [])

#########################################
if __name__ == '__main__':
	main()
