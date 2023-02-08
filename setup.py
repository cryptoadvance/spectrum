from setuptools import setup, find_namespace_packages

with open("requirements.txt") as f:
    install_reqs = f.read().strip().split("\n")

# Filter out comments/hashes
requirements = [
    req.rstrip(" \\")
    for req in install_reqs
    if req.rstrip(" \\")
    and not req.startswith("#")  # comments
    and not req.strip().startswith("--hash=")  # hash of the package
]

setup(
    packages=find_namespace_packages("src", include=["cryptoadvance.*"]),
    package_dir={"": "src"},
    package_data={},
    # take METADATA.in into account, include that stuff as well (static/templates)
    include_package_data=True,
    install_requires=requirements,
)
