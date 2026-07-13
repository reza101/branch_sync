from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = [l.strip() for l in f if l.strip() and not l.startswith("#")]

setup(
    name="branch_sync",
    version="0.1.0",
    description="Branch ↔ Center sync for multi-branch pharmacy",
    author="webmajors",
    author_email="webmajors.com@gmail.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
