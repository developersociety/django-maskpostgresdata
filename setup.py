from setuptools import setup

setup(name='django-maskpostgresdata',
      version='0.1',
      description='Creates a pg_dumpish output which masks data without saving changes to the source database.',
      url='https://github.com/developersociety/django-maskpostgresdata',
      author='Alistair Clrk',
      author_email='alistair@dev.ngo',
      license='MIT',
      packages=['funniest'],
      zip_safe=False)
