# -*- coding: utf-8 -*-
# cheby_checker/cheby_checker/sql.py

'''
    --------------------------------------------------------------
    cheby_checker's sqlite module.
    
    Aug 2020
    Matt Payne
    
    This module provides functionalities to interact with
    (i) The tables related to storing ephemeris representations
        - I.e. chebyshev representations
    (ii) The table(s) related to storing the ITF data for
        - SIFTER
    
    --------------------------------------------------------------
'''


# Import third-party packages
# --------------------------------------------------------------
import sys, os
import numpy as np
import sqlite3
from sqlite3 import Error
import pickle

# Import neighboring packages
# --------------------------------------------------------------
# cheby_checker/                 # <<-- repo
# cheby_checker/cheby_checker    # <<-- python
# cheby_checker/tests            # <<-- tests
this_dir = os.path.abspath(os.path.dirname( __file__ ))
repo_dir = os.path.abspath(os.path.dirname( this_dir ))
test_dir = os.path.join(repo_dir, 'tests')
code_dir = os.path.join(repo_dir, 'cheby_checker')
for d in [test_dir, code_dir]:
    sys.path.append( d )
from cheby_checker import Base



# Data classes/methods
#
# N.B. Many of these sqlite functions are copied straight from
# https://www.sqlitetutorial.net/sqlite-python/
# E.g.
# https://www.sqlitetutorial.net/sqlite-python/creating-database/
# https://www.sqlitetutorial.net/sqlite-python/create-tables/
# ...
#
# -------------------------------------------------------------

class DB():

    def __init__(self,):
        self.db_file = self.fetch_db_filepath()
        self.conn    = self.create_connection()


    @staticmethod
    def fetch_db_filepath():
        '''
        '''
        B = Base()
        db_dir = B._fetch_data_directory()
        return os.path.join(db_dir , B.db_filename)

    def create_connection(self,):
        """ Create a database connection to the SQLite database
            specified by db_file
            
            inputs:
            -------
            db_file: database file
            
            return:
            -------
            Connection object or None
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_file)
            return conn
        except Error as e:
            print(e)
        
        return conn


    def create_table(self, create_table_sql ):
        """ Create a table from the create_table_sql statement
            
            inputs:
            -------
            conn: Connection object
            
            create_table_sql: a CREATE TABLE statement
            
            return:
            -------
        """
        try:
            c = self.conn.cursor()
            c.execute(create_table_sql)
        except Error as e:
            print(e)


class SQLChecker(DB):

    def __init__(self,):
        super().__init__()


    # ---------------------------------------------
    # Generic functionalities
    # ---------------------------------------------

    def generate_sector_field_names(self,  sector_dict = Base().get_required_sector_dict() ):
        '''  Dynamically generate the field-specs that will be required for the coeffs-by-sector  '''
        return [ 'sector_%d_%d' % (i, jd) for i, jd in sector_dict.items() ]

    def generate_blank_coefficient_dict(self,  sector_dict = Base().get_required_sector_dict() ):
        '''  Generate a blank default dictionary for upsert to coeffs table ...  '''
        return { _ : None for _ in self.generate_sector_field_names() }

    # ---------------------------------------------
    # Create the *CHECKER* tables
    # ---------------------------------------------
    def create_all_checker_tables(self,):
        self.create_object_coefficients_table()
        self.create_objects_by_jdhp_table()
        

    def create_object_coefficients_table(self,):
        """ Create the object_coefficients table(s) that we need for ephemeris calcultions
            
            Created table has columns that look like
                object_coeff_id                             : integer
                primary_unpacked_provisional_designation    : text
                sector_%d_%d                                : text blob      <<-- *MANY* of these sectors
                
                
            *** WHY DO WE WANT/NEED THE TABLE TO HAVE MANY MANY SECTOR FIELSD ???***
            *** WHY NOT JUST HAVE 3 FIELDS: (a) SECTOR #/ID, (b) desig, AND (c) COEFFICIENTS ???      ***
            """
        
        
        # Create table ...
        # Needs many fields, one per coefficient-set
        #  - Dynamically generate the field-specs that will be required for the coeffs-by-sector ...
        #  - This will look like ... sector_0_2440000 blob , sector_1_2440032 blob, ...
        sector_names = self.generate_sector_field_names()
        sector_spec  = " blob, ".join( sector_names )
        sector_spec  = sector_spec + " blob"
        
        sql_statement = """
            CREATE TABLE IF NOT EXISTS object_coefficients (
            object_coeff_id INTEGER PRIMARY KEY,
            primary_unpacked_provisional_designation TEXT UNIQUE NOT NULL,""" + \
                sector_spec + "); "   # <<-- Lots of extra fields in here!!!
            
        if self.conn is not None:
            # Create table
            self.create_table( sql_statement )
            
            # Create indicex on designation
            createSecondaryIndex =  "CREATE INDEX index_desig ON object_coefficients (primary_unpacked_provisional_designation);"
            self.conn.cursor().execute(createSecondaryIndex)


    def create_objects_by_jdhp_table(self,):
        """ Create the specific objects_by_jdhp table that we need for *mpchecker2*
            
            Created table has columns that look like
                            jdhp_id     : integer
                            jd          : integer
                            hp          : integer
                            object_coeff_id   : integer
                
            """

        # Create table ...
        sql_statement = """ CREATE TABLE IF NOT EXISTS objects_by_jdhp (
            jdhp_id INTEGER PRIMARY KEY,
            jd INTEGER NOT NULL,
            hp INTEGER NOT NULL,
            object_coeff_id INTEGER NOT NULL
            ); """
        
        
        # create table(s)
        if self.conn is not None:
            
            # create tables
            self.create_table( sql_statement )
            
            # Create indicees
            createSecondaryIndex =  "CREATE INDEX index_jdhp ON objects_by_jdhp (jd, hp);"
            self.conn.cursor().execute(createSecondaryIndex)
            createSecondaryIndex =  "CREATE INDEX index_object_coeff_id ON objects_by_jdhp (object_coeff_id);"
            self.conn.cursor().execute(createSecondaryIndex)


    # --------------------------------------------------------
    # --- Funcs to write to / update CHECKER db-tables
    # --------------------------------------------------------

    def upsert_coefficients(self, primary_unpacked_provisional_designation , sector_names, sector_values):
        """
            Insert/Update coefficients in the *object_coefficients* table
            
            N.B.
             - I am making the design decision to always replace all of the sectors
             - If *all* sectors are initially populated and then an update wants to update a *subset*, then we
               would risk having incompatible data, so in that scenario I would want to blank-out all of the
               sectors that were not explicitly being updated
             - The way I can think of to do this at present is to have default values that are always blank...

            inputs:
            -------
            
            primary_unpacked_provisional_designation : string

            sector_names :
             - column names in *object_coefficients* table that are to be populated
             
            sector_values :
             - column values corresponding to the sector_names in *object_coefficients* table that are to be populated

            return:
            -------
            
        """
        # Make a default insert disct that contains ...
        # (a) the designation
        # (b) all the sector fields with "None" values
        insert_dict = {'primary_unpacked_provisional_designation':primary_unpacked_provisional_designation}
        
        # Check inputs ...
        assert isinstance(primary_unpacked_provisional_designation, str) \
            and len(sector_names)==len(sector_values)
        
        # Update the coeff dict using the input values
        insert_dict.update( {k:v for k,v in zip(sector_names, sector_values) } )
        
        # Construct an sql insert statement
        # NB(1): Because the primary_unpacked_provisional_designation field is unique, this should enforce replacement on duplication
        # NB(2): It completely deletes the initial row, then replaces it with the new stuff
        columns      = ', '.join(insert_dict.keys())
        placeholders = ':'+', :'.join(insert_dict.keys())
        query = 'REPLACE INTO object_coefficients (%s) VALUES (%s)' % (columns, placeholders)

        # Execute the upsert ...
        cur = self.conn.cursor()
        cur.execute(query, insert_dict)
        self.conn.commit()
        
        # Return the id of the row inserted
        object_coeff_id = cur.lastrowid
        return object_coeff_id



   

    def insert_HP(self, JDlist, HPlist, object_id ):
        """
            objects_by_jdhp is structured like ...
                            jdhp_id     : integer
                            jd          : integer
                            hp          : integer
                            object_coeff_id   : integer
                
            inputs:
            -------
            JDlist :
            
            HPlist :
            
            object_id : integer

        """
        cur = self.conn.cursor()

        # Sense-check
        assert len(JDlist)==len(HPlist), 'len(JDlist)!=len(HPlist) [%d != %d] in insert_HP' % (len(JDlist),len(HPlist))

        # *** Delete old entries ***
        # - My assumption here is that if we are inserting entries for a known object, we have likely calculated a new orbit
        # - Hence for sanitary reasons we should delete the old ones and replace with the new.
        self.delete_JDHP_by_object_coeff_id( object_id )
        
        # Insert new ...
        # (a) construct "records" variable which is apparently ammenable to single insert statement ...
        # https://pythonexamples.org/python-sqlite3-insert-multiple-records-into-table/
        # Note the use of "int" to force the numpy variables to play nicely with sql
        records = [ (int(jd), int(hp), object_id) for jd,hp in zip(JDlist,HPlist) ]
        
        # (b) construct sql string
        sqlstr = '''INSERT INTO objects_by_jdhp(jd,hp,object_coeff_id) VALUES(?,?,?);'''
        
        # (c) Insert
        cur.executemany(sqlstr, records)
        
        # (d) remember to commit ...
        self.conn.commit()




    # --------------------------------------------------------
    # --- Funcs to delete data
    # --------------------------------------------------------

    def delete_JDHP_by_object_coeff_id(self, object_coeff_id):
        """
            Delete all rows from "objects_by_jdhp" that match the supplied "object_coeff_id"
        """
        cur = self.conn.cursor()

        # Construct & execute the sql query
        # - This is matching/joining on object-id# and then deleting only from objects_by_jdhp
        #   (and leaving the entry in object_desig)
        cur.execute( " DELETE FROM objects_by_jdhp WHERE object_coeff_id=?;", (int(object_coeff_id),) )
        self.conn.commit()



    # --------------------------------------------------------
    # --- Funcs to query db-tables
    # --------------------------------------------------------

    def query_object_coefficients(self,
                                    primary_unpacked_provisional_designation,
                                    sector_numbers = None):
        """
           Define standard query used to get cheby-coeff data for a named object
           Can optionally select only a subset of sectors
           
           inputs:
           -------
            primary_unpacked_provisional_designation: string
        
            sector_numbers: integer
        
           
           return:
           -------
           list of numpy-arrays
            - Each numpy-array item is a set of cheby-coeffs for a specific sector

        """
        cur = self.conn.cursor()
        
        # What sector numbers are we searching for ?
        # - Default is to get data for all of them
        if sector_numbers is None :
            sector_field_names = self.generate_sector_field_names()
        else:
            sector_field_names = self.generate_sector_field_names( sector_dict = {
                                                                sector_num: sector_JD for \
                                                                sector_num, sector_JD in zip(sector_numbers ,
                                                                                            Base().map_sector_number_to_sector_start_JD(np.atleast_1d(sector_numbers) ,\
                                                                                            Base().standard_MJDmin))})
        # Construct & execute the sql query
        sqlstr = "SELECT " + ", ".join( sector_field_names ) + " FROM object_coefficients WHERE primary_unpacked_provisional_designation=?"
        cur.execute(sqlstr , ( primary_unpacked_provisional_designation, ))

        # Parse the result ...
        result = cur.fetchall()[0]
        return { sfn:pickle.loads( coeff )  for sfn, coeff in zip(sector_field_names, result) if coeff != None }




    def query_desig_by_object_coeff_id(self, object_coeff_ids):
        """
        Given a list of object_ids, return the associated primary_unpacked_provisional_designations

        inputs:
        -------
        object_ids: list of integer object_ids

        return:
        -------
        dictionary
         - maps object_id (key) to designation (value)

        """
        # Get the object_id & return it
        cur = self.conn.cursor()
        cur.execute(f'''SELECT object_coeff_id, primary_unpacked_provisional_designation FROM object_coefficients WHERE object_coeff_id in ({','.join(['?']*len(object_coeff_ids))});''', (*(int(_) for _ in object_coeff_ids),) )
        
        # key is object_coeff_id, value is desig
        return {_[0]:_[1] for _ in cur.fetchall()}



    def query_coefficients_by_jd_hp(self, JD, HPlist , sector_numbers = None):
        '''
            For a given (single) JD and list of Healpix,
            the query returns the relevant coefficients from the object_coefficients table
            
            inputs
            ------
            JD: float or int
             - julian date of the night. If <float> will be silently converted to <int>
             
            HPlist: list-of-integers
             - healpix to be queried
             - if integer (single healpix) supplied, is silently converted to list
             
            returns
            -------
            dictionary-of-dictionaries
            - keys   = primary_unpacked_provisional_designation
            - values = list of coeff-dictionaries for each primary_unpacked_provisional_designation
        '''
        
        # What sector numbers are we searching for ?
        # - Default is to get data for all of them
        if sector_numbers is None :
            sector_field_names = self.generate_sector_field_names()
        else:
            sector_field_names = self.generate_sector_field_names( sector_dict = {
                                                             sector_num: sector_JD for \
                                                             sector_num, sector_JD in zip(sector_numbers ,
                                                                                          Base().map_sector_number_to_sector_start_JD(np.atleast_1d(sector_numbers) ,\
                                                                                                                                                  Base().standard_MJDmin))})
        # Construct & execute the sql query
        sqlstr =    "SELECT object_coefficients.primary_unpacked_provisional_designation," + \
                    ", ".join( sector_field_names ) + \
                    f" FROM object_coefficients INNER JOIN objects_by_jdhp ON objects_by_jdhp.object_coeff_id = object_coefficients.object_coeff_id WHERE objects_by_jdhp.jd=? and objects_by_jdhp.hp in ({','.join(['?']*len(HPlist))})"
        cur = self.conn.cursor()
        cur.execute(sqlstr , (int(JD), *(int(_) for _ in HPlist), ))

        # Parse the result into a dict-of-dicts
        # - Outer dict is key-ed on primary_unpacked_provisional_designation
        # - Inner dicts are key-ed on sector
        results      = cur.fetchall()
        return { r[0] : { sfn:pickle.loads( coeff )  for sfn, coeff in zip(sector_field_names, r[1:]) if coeff != None } \
                for r in results}





    def query_jd_hp(self, JD, HPlist):
        '''
            For a given (single) JD and list of Healpix,
            the query returns the relevant object_coeff_ids
            
            May be of little use in practice, but helpful for development
            
        '''
        # Connection cursor
        cur = self.conn.cursor()

        # This will get the unique object-IDs
        # I hate this fucking query for many reasons ...
        # (i) Why the fuck do I need to force any input numpy-integers, to be integers ???
        #(ii) Why the fuck do I need to explicitly expand the number of "?" in the "in ()" statement ???
        cur.execute(f"SELECT object_coeff_id FROM objects_by_jdhp WHERE jd=? and hp in ({','.join(['?']*len(HPlist))});", (int(JD), *(int(_) for _ in HPlist), ) )
        #object_ids = [_[0] for _ in cur.fetchall()]
        return [_[0] for _ in cur.fetchall()]





class SQLSifter(DB):
    
    def __init__(self,):
        super().__init__()


    # ---------------------------------------------
    # Generic functionalities
    # ---------------------------------------------

    # ---------------------------------------------
    # Create the *CHECKER* tables
    # ---------------------------------------------
    def create_sifter_tables(conn):
        """ Create the specific table(s) that we need for *sifter*
            Currently creates:
            (i) tracklets

            inputs:
            -------
            conn: Connection object

            return:
            -------

        """
        
        # Note that I am deliberately setting up the stored *tracklet* data as a "blob"
        # - Because not yet sure what will be in it!
        sql_create_tracklets_table = """ CREATE TABLE IF NOT EXISTS tracklets (
            id integer PRIMARY KEY,
            jd integer NOT NULL,
            hp integer NOT NULL,
            tracklet_name text NOT NULL,
            tracklet blob
            ); """
        
        # create table(s)
        if conn is not None:
            
            # create "jdhp_to_tracklet" table
            create_table(conn, sql_create_tracklets_table)

            # Create compound/combined index on the jd & hp columns
            createSecondaryIndex =  "CREATE INDEX index_jdhp ON tracklets (jd, hp);"
            conn.cursor().execute(createSecondaryIndex)
        
        # remember to commit ...
        conn.commit()


    # --------------------------------------------------------
    # --- Funcs to write to / update SIFTER db-tables
    # --------------------------------------------------------
    def upsert_tracklet(conn, jd, hp, tracklet_name, tracklet_dict):
        """
            insert/update tracklet data
            
            N.B ...
            https://stackoverflow.com/questions/198692/can-i-pickle-a-python-dictionary-into-a-sqlite3-text-field
            pdata = cPickle.dumps(data, cPickle.HIGHEST_PROTOCOL)
            curr.execute("insert into table (data) values (:data)", sqlite3.Binary(pdata))

            inputs:
            -------
            conn: Connection object
            
            jd :
            hp :
            tracklet_name :
            tracklet_dict :
            
            return:
            -------
            
        """
        
        # Make cursor ...
        cur = conn.cursor()
        
        # Construct sql for tracklet insert ...
        sql =  ''' INSERT OR REPLACE INTO tracklets(jd,hp,tracklet_name,tracklet)
            VALUES(?,?,?,?)
            '''
        
        # Insert
        cur.execute(sql, (jd, hp, tracklet_name, sqlite3.Binary( pickle.dumps(tracklet_dict, pickle.HIGHEST_PROTOCOL) ),))

        # remember to commit ...
        conn.commit()


    def upsert_tracklets(conn, jd_list, hp_list, tracklet_name_list, tracklet_dict_list):
        """
            insert/update lists of tracklet data
            
            N.B ...
            https://stackoverflow.com/questions/198692/can-i-pickle-a-python-dictionary-into-a-sqlite3-text-field
            pdata = cPickle.dumps(data, cPickle.HIGHEST_PROTOCOL)
            curr.execute("insert into table (data) values (:data)", sqlite3.Binary(pdata))
            
            inputs:
            -------
            conn: Connection object
            
            jd_list :
            hp_list :
            tracklet_name_list :
            tracklet_dict_list :
            
            return:
            -------
            
            """
        # Make cursor ...
        cur = conn.cursor()

        # construct "records" variable which is apparently ammenable to single insert statement ...
        # https://pythonexamples.org/python-sqlite3-insert-multiple-records-into-table/
        records = [ (int(jd), int(hp), tracklet_name, sqlite3.Binary(pickle.dumps(tracklet_dict, pickle.HIGHEST_PROTOCOL))) \
                   for jd, hp, tracklet_name, tracklet_dict \
                   in zip(jd_list, hp_list, tracklet_name_list, tracklet_dict_list) ]

        sql = '''INSERT OR REPLACE INTO tracklets(jd,hp,tracklet_name,tracklet) VALUES(?,?,?,?);'''

        # Insert
        cur.executemany(sql, records)

        # remember to commit ...
        conn.commit()


    # --------------------------------------------------------
    # --- Funcs to delete from SIFTER db-tables
    # --------------------------------------------------------
    def delete_tracklet(conn, tracklet_name):
        """
            delete tracklet data
            
            inputs:
            -------
            tracklet_name: string
            
            return:
            -------
            
            
        """
        sql = 'DELETE FROM tracklets WHERE tracklet_name=?'
        cur = conn.cursor()
        cur.execute(sql, (tracklet_name,))
        conn.commit()


    def delete_tracklets(conn, tracklet_name_list):
        """
            delete list of tracklet data
            
            inputs:
            -------
            tracklet_name: list-of-strings
            
            return:
            -------
            
            
            """
        sql = '''DELETE FROM tracklets WHERE tracklet_name IN (?);'''
        records = [ (tracklet_name,) for tracklet_name in tracklet_name_list ]
        cur = conn.cursor()
        cur.executemany(sql, records)
        conn.commit()


    # --------------------------------------------------------
    # --- Funcs to query SIFTER db-tables
    # --------------------------------------------------------
    def query_tracklets_jdhp(conn, JD, HP):
        """
           Standard query used to find all tracklets for which jd,hp matches input
           
           inputs:
           -------
           JD: integer
           HP: integer
           
           return:
           -------
           list of tracklet_names

        """
        cur = conn.cursor()
        cur.execute("SELECT tracklet_name, tracklet FROM tracklets WHERE jd=? AND hp=?", ( int(JD), int(HP) , ))
        
        # return a list-of-tuples: (tracklet_name, tracklet_dictionary)
        return [ (row[0] , pickle.loads( row[1] ) ) for row in cur.fetchall() ]


    def query_tracklets_jd_hplist(conn, JD, HP_list):
        """
            Standard query used to find all tracklets for which jd,hp_list matches input
            
            inputs:
            -------
            JD: integer
            HP_list: list-of-integers
            
            return:
            -------
            list of tracklet_names
            
            """
        assert isinstance(JD, int) and isinstance(HP_list, list), 'Cannot parse input types in query_tracklets_jd_hplist ... '

        # Get cursor ...
        cur = conn.cursor()

        # Set up query:
        #N.B. https://stackoverflow.com/questions/18363276/how-do-you-do-an-in-query-that-has-multiple-columns-in-sqlite
        for sql in ['''CREATE TEMPORARY TABLE lookup(jd, hp);''',
                    '''INSERT OR REPLACE INTO lookup(jd,hp) VALUES(?,?);''',
                    '''CREATE INDEX lookup_jd_hp ON lookup(jd, hp);''',
                    '''SELECT tracklet_name, tracklet FROM tracklets JOIN lookup ON tracklets.jd = lookup.jd AND tracklets.hp = lookup.hp;''']:
            
            # Execute queries
            print( ' ... = ', sql )
            if 'INSERT' in sql:
                records = [ (JD, hp) for hp in HP_list ]
                cur.executemany(sql, records )
            else:
                cur.execute(sql)

        # return a list-of-tuples: (tracklet_name, tracklet_dictionary)
        return [ (row[0] , pickle.loads( row[1] ) ) for row in cur.fetchall() ]





