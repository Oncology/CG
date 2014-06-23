#!/usr/bin/python

import sys, os
import MySQLdb
from   tcga_utils.mysql   import  *

#########################################
def main():
    
    db     = connect_to_mysql()
    cursor = db.cursor()

    db_name  = 'COAD'
    table = 'somatic_mutations'

    switch_to_db (cursor, db_name)

    # unbuffered output
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

    ############################
    print db_name, table, "number of entries:"
    qry = "select count(1) from " + table
    rows = search_db(cursor, qry)
    print "\t", rows[0][0]
    print 
    ############################

    ############################
    print "number of entries without tumor barcode:"
    qry  = "select count(1) from somatic_mutations "
    qry += "where not TumorSampleBarcode like 'TCGA%'"
    rows = search_db(cursor, qry)
    print "\t", rows[0][0]
    print 
    ############################

    ############################
    print "sorting per-patient data ..."
    uniq_patients = {}
    qry  = "select TumorSampleBarcode from somatic_mutations "
    rows = search_db(cursor, qry)
    for  row in rows:
        tbarcode = row[0]
        # the fields are 
        # project - tissue source site (TSS)  - participant -
        # source.vial - portion.analyte  - plate - (sequenncing or charcterization center)
        fields = tbarcode.split('-')
        patient = '-'.join(fields[1:3])
        if not  uniq_patients.has_key(patient):
            uniq_patients[patient] = []
        uniq_patients[patient].append('-'.join(fields[3:]))

    print "number of different patients:", len(uniq_patients)
    print
    ############################

    ############################
    # sort by the number of entries
    print "number of different samples per patient:"
    patients_sorted = sorted(uniq_patients.keys(), key= lambda x: len( uniq_patients[x]) )
    for patient in patients_sorted:
        samples = uniq_patients[patient]
        print patient, len(samples)
        uniq_samples = {}
        for sample in samples:
            if not  uniq_samples.has_key(sample):
                uniq_samples[sample] = 0
            uniq_samples[sample] += 1
        if len(uniq_samples) >1:
            
            for sample in  uniq_samples.keys():
                print "\t", sample, uniq_samples[sample]
           


    cursor.close()
    db.close()


#########################################
if __name__ == '__main__':
    main()

