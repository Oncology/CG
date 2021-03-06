#! /usr/bin/python

from icgc_utils.common_queries import *
import random

def main():

	db     = connect_to_mysql()
	cursor = db.cursor()

	# all protein coding genes
	genes, chrom = protein_coding_genes(cursor)

	switch_to_db(cursor,'icgc')
	snvs = {}
	silent_ratio = {}
	#for gene in random.sample(genes,1000):
	for gene in genes:
		#silent
		qry  = "select count(*) from mutation2gene g, mutations_chrom_%s  m where g.gene_symbol='%s' "  % (chrom[gene], gene)
		qry += "and m.icgc_mutation_id=g.icgc_mutation_id and  m.consequence = 'synonymous' and m.reliability_estimate=1"
		ret = search_db(cursor,qry, verbose=True)
		if ret:
			silent = ret[0][0]
		else:
			silent = 0

		# other
		qry  = "select count(*) from mutation2gene g, mutations_chrom_%s  m where g.gene_symbol='%s' "  % (chrom[gene], gene)
		qry += "and m.icgc_mutation_id=g.icgc_mutation_id and  m.consequence in ('missense','stop_gained') "
		qry += "and m.reliability_estimate=1"
		ret = search_db(cursor,qry, verbose=True)
		if ret:
			other = ret[0][0]
		else:
			other = 0

		if silent==0 and other==0: continue
		#if silent+other<50: continue
		if silent==0:
			silent_ratio[gene] = 0.0
		else:
			silent_ratio[gene] = float(silent)/(silent+other)
		snvs[gene] = silent+other

	gene_ratio_list =[(gene,ratio) for gene,ratio in sorted(silent_ratio.iteritems(), key=lambda (k,v): v)]

	for gene,ratio in gene_ratio_list[:100]:
		print "%15s  %5.2f  %4d " % (gene, ratio, snvs[gene])

	outf = open ("silent_ratio.tsv","w")
	for gene,ratio in gene_ratio_list:
		outf.write("\t".join([gene, "%.4f"%ratio, "%d"%snvs[gene]])+"\n")
	outf.close()

	cursor.close()
	db.close()



#########################################
if __name__ == '__main__':
	main()
