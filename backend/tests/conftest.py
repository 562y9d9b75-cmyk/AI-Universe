"""Choose isolated app storage before any test imports the database module."""
import os
import tempfile

_test_data=tempfile.mkdtemp(prefix='aiu-suite-')
os.environ['AIU_DATA_DIR']=_test_data
os.environ['AIU_DATABASE_URL']='sqlite:///'+_test_data+'/test.db'
os.environ['AIU_REDIS_URL']=''
