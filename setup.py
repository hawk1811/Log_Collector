from setuptools import setup, find_packages

setup(
    name="log_collector",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0",
        "psutil>=5.8.0",
        "prompt_toolkit>=3.0.20",
        "colorama>=0.4.4",
    ],
    entry_points={
        "console_scripts": [
            "log_collector=log_collector.main:main",
        ],
    },
    python_requires=">=3.7",
    author="K.G - The Hawk",
    author_email="the.hawk1811@gmail.com",
    description="High-performance log collection and processing system",
    keywords="logging, monitoring, data collection",
    url="https://github.com/logcollector/log_collector",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Logging",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)
