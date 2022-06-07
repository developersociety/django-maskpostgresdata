from setuptools import find_packages, setup

with open('README.md') as f:
    long_description = f.read()

setup(
    name='django-maskpostgresdata',
    packages=find_packages(),
    version='0.1.15',
    description=(
        'Creates a pg_dumpish output which masks data without saving changes to the source '
        'database.'
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/developersociety/django-maskpostgresdata',
    author='Developer Society',
    author_email='hello@dev.ngo',
    license='BSD',
    zip_safe=False,
    install_requires=['django>=1.8']
)
