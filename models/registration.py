# This tracks the current active registration series.
# A series looks like: KA01AB — numbers go from 0001 to 9999.
# When 9999 is reached, a new series starts (KA01AB → KA01AC etc.)

class RegistrationSeries:
    def __init__(self, series_prefix, fancy_numbers=None):
        """
        series_prefix: e.g. "KA01AB" — the letters part of the plate
        fancy_numbers: a dictionary of {number: tier}
                       e.g. {1: 1, 786: 2, 1111: 1}
                       tier 1 = Rs 1,00,000 minimum bid
                       tier 2 = Rs 50,000 minimum bid
                       tier 3 = Rs 25,000 minimum bid
        """
        self.series_prefix = series_prefix
        self.current_number = 0          # starts at 0, first issued will be 0001
        self.fancy_numbers = fancy_numbers if fancy_numbers else {}
        self.auctioned_numbers = {}      # {number: winning_bid} — fancy numbers sold via auction
        self.issued_numbers = set()      # set of numbers that have already been issued
        self.is_exhausted = False        # True when 9999 is reached

    def format_mark(self, number):
        """
        Converts a number like 1 into a full plate like "KA01AB0001".
        Always 4 digits with leading zeros.
        """
        return f"{self.series_prefix}{number:04d}"

    def is_fancy(self, number):
        """Returns True if this number is in the fancy list."""
        return number in self.fancy_numbers

    def get_fancy_tier(self, number):
        """Returns the tier (1, 2, or 3) of a fancy number."""
        return self.fancy_numbers.get(number, None)

    def __str__(self):
        return f"Series({self.series_prefix}, current={self.current_number:04d})"