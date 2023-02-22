from setuptools import setup, find_namespace_packages

setup(
    packages=find_namespace_packages("src", include=["cryptoadvance.*"]),
    package_dir={"": "src"},
    package_data={},
    # take METADATA.in into account, include that stuff as well (static/templates)
    include_package_data=True,
)
