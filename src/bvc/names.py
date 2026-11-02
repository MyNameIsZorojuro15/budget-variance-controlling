"""English display names for the federal budget's Einzelpläne (ministries) and economic categories.

The data carry the official German names; these labels are for reading. Names follow the latest published
plan, so a ministry keeps its current name in earlier years even where its remit was different.
"""
EP_EN = {
    "01": "Federal President", "02": "Bundestag", "03": "Bundesrat", "04": "Chancellery",
    "05": "Foreign Office", "06": "Interior", "07": "Justice and Consumer Protection", "08": "Finance",
    "09": "Economic Affairs and Energy", "10": "Agriculture, Food and Homeland", "11": "Labour and Social Affairs",
    "12": "Transport", "14": "Defence", "15": "Health", "16": "Environment and Climate Action",
    "17": "Education, Family, Seniors, Women, Youth", "19": "Federal Constitutional Court",
    "20": "Federal Court of Audit", "21": "Data Protection Commissioner", "22": "Independent Control Council",
    "23": "Economic Cooperation and Development", "24": "Digital and State Modernisation",
    "25": "Housing, Urban Development, Building", "30": "Research, Technology and Space",
    "32": "Federal Debt", "60": "General Financial Administration",
}

HGR_EN = {
    ("expenses", "4"): "Personnel",
    ("expenses", "5"): "Operating costs, military procurement, debt service",
    ("expenses", "6"): "Grants and transfers (non-investment)",
    ("expenses", "7"): "Construction",
    ("expenses", "8"): "Other investment and investment grants",
    ("expenses", "9"): "Special financing (incl. global savings targets)",
}


def localize(df, ep_col: str = "ep_label"):
    """Replace the German ministry name by the English one where a ministry number is known."""
    if "ep_id" in df.columns and ep_col in df.columns:
        df = df.copy()
        df[ep_col] = df["ep_id"].map(EP_EN).fillna(df[ep_col])
    return df
