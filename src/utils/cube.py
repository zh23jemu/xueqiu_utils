from collections import defaultdict


def find_duplicate_holdings(portfolios):
    """
    Finds duplicate holdings across multiple portfolios.

    Parameters:
    - portfolios (list): A list of tuples, where each tuple represents a portfolio and contains the portfolio name and a list of stocks.

    Returns:
    - dict: A dictionary where keys are stocks that are held in multiple portfolios, and values are the names of the portfolios they are held in.
    """
    stock_to_portfolios = defaultdict(list)

    # Build mapping: stock → portfolios
    for portfolio_name, stocks in portfolios:
        for stock in stocks:
            stock_to_portfolios[stock].append(portfolio_name)

    # Keep only stocks that appear in multiple portfolios
    duplicates = {stock: names for stock, names in stock_to_portfolios.items() if len(names) > 1}
    return duplicates
