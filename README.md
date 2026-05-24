# Coffee-Futures

Analysis of Coffee Futures Markets

## Overview

This project provides tools and analysis for coffee futures data, including data loading, statistical analysis, and visualization capabilities.

## Project Structure

```
Coffee-Futures/
├── src/coffee_futures/     # Main package
│   ├── __init__.py
│   ├── analysis.py         # Analysis functions
│   └── data.py             # Data loading utilities
├── tests/                  # Unit tests
│   ├── __init__.py
│   └── test_analysis.py
├── notebooks/              # Jupyter notebooks
├── data/                   # Data files directory
├── requirements.txt        # Python dependencies
├── setup.py               # Package setup configuration
├── pyproject.toml         # Modern Python project config
├── .gitignore             # Git ignore rules
└── README.md              # This file
```

## Installation

### Development Installation

```bash
# Clone the repository
git clone https://github.com/simile865/Coffee-Futures.git
cd Coffee-Futures

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"
```

### Dependencies

- pandas >= 1.3.0
- numpy >= 1.21.0
- matplotlib >= 3.4.0
- seaborn >= 0.11.0
- jupyter >= 1.0.0

## Usage

### Basic Analysis

```python
from coffee_futures import load_data, analyze_futures

# Load data
data = load_data('data/coffee_prices.csv')

# Analyze futures
results = analyze_futures(data)
print(results)
```

## Testing

Run tests using pytest:

```bash
pytest tests/
```

Run with coverage:

```bash
pytest --cov=coffee_futures tests/
```

## Contributing

Contributions are welcome! Please follow these steps:

1. Create a new branch for your feature
2. Make your changes
3. Write/update tests
4. Submit a pull request

## License

This project is licensed under the MIT License - see LICENSE file for details.

## Author

simile865 (qxu2023@gmail.com)
