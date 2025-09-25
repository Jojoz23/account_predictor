from setuptools import setup, find_packages

setup(
    name="account-predictor",
    version="0.1.0",
    description="Machine Learning model to predict account categories from transaction data",
    author="Your Name",
    packages=find_packages(),
    install_requires=[
        "pandas>=2.1.0",
        "numpy>=1.24.0",
        "scikit-learn>=1.3.0",
        "matplotlib>=3.8.0",
        "seaborn>=0.13.0",
        "plotly>=5.17.0",
        "nltk>=3.8.0",
        "spacy>=3.7.0",
        "wordcloud>=1.9.0",
        "xgboost>=2.0.0",
        "lightgbm>=4.1.0",
        "joblib>=1.3.0",
    ],
    python_requires=">=3.8",
)

