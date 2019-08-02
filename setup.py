from setuptools import setup

def readme():
    with open('README.rst') as f:
        return f.read()

setup(
    name='django-maskpostgresdata',
    packages=['maskpostgresdata'],
    version='0.1.2',
    description='Creates a pg_dumpish output which masks data without saving changes to the source database.',
    url='https://github.com/developersociety/django-maskpostgresdata',
    author='Developer Society',
    author_email='hello@dev.ngo',
    license='BSD',
    zip_safe=False,
    install_requires = ['django>=1.8','psycopg2']
)
