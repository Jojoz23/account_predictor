# Account Predictor

A machine learning model that predicts account categories from transaction data (date, description, and amount).

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start Jupyter notebook:
```bash
jupyter notebook
```

## Project Structure

- `data/` - Raw and processed transaction data
- `notebooks/` - Jupyter notebooks for analysis and model development
- `src/` - Source code for data processing and model training
- `models/` - Trained model files
- `results/` - Model evaluation results and visualizations

## Data Collection

Start by collecting your bookkeeping data in the `data/` directory. The model expects transaction data with:
- Date
- Description
- Account (target variable for training)
- Amount

