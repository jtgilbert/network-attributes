from setuptools import setup
import re

# https://packaging.python.org/discussions/install-requires-vs-requirements/
install_requires = [
    'numpy>=1.23', 'GDAL>3.0', 'geopandas>=0.12', 'Shapely==1.8.5.post1', 'rasterstats==0.17.0', 'rasterio==1.3.4',
    'pysheds==0.3.3'
]

with open("README.md", "rb") as f:
    long_descr = f.read().decode("utf-8")

version = re.search(
    '^__version__\\s*=\\s*"(.*)"',
    open('tools/__version__.py').read(),
    re.M
).group(1)

setup(
    name='network-attributes',
    version=version,
    packages=['tools'],
    url='https://github.com/jtgilbert/network-attributes',
    license='MIT',
    author='Jordan Gilbert',
    author_email='jtgilbert89@gmail.com',
    description='tools for segmenting and adding attributes to drainage networks',
    python_requires='>3.8',
    long_description=long_descr,
    install_requires=install_requires,
    zip_safe=False,
    entry_points={
          "console_scripts": [
              'drainage_area = tools.drainage_area:main',
              'flow_scaling = tools.flow_scaling:main',
              'network_topology = tools.network_topology:main',
              'segment_network = tools.segment_network:main',
              'sinuosity = tools.sinuosity:main',
              'slope = tools.slope:main'
          ]
      }
)
