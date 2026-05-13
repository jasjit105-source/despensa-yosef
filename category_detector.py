CATEGORIES = [
    ("Wines & Spirits", [
        "wine", "concord", "moscato", "malaga", "niagara", "claret",
        "cream red", "cream pink", "cream rose", "cream malaga", "cream niagara",
        "merlot", "cabernet", "chardonnay", "pinot", "sacramental", "joyvin",
        "farbrengen", "melody", "teperberg", "etzion", "king david",
    ]),
    ("Snacks & Cookies", [
        "cookie", "biscuit", "wafer", "pretzel", "chip", "cracker",
        "animal cookies", "onion rings", "cereal bar",
    ]),
    ("Candy & Chocolate", [
        "chocolate", "candy", "gummy", "lollipop", "taffy", "sour sticks",
        "sour bites", "caramel", "nougat", "coin", "dreidel", "klik",
        "wowzers", "zillions", "fruzips", "trios", "shotz", "solos",
        "silhouette", "kariot", "pesek zman",
    ]),
    ("Condiments & Sauces", [
        "vinegar", "dressing", "sauce", "ketchup", "mustard", "mayo",
        "salsa", "balsamic", "marinara",
    ]),
    ("Pasta & Grains", [
        "pasta", "gnocchi", "noodle", "rice", "couscous", "spaghetti",
        "penne", "fusilli", "farfalle",
    ]),
    ("Canned & Jarred", [
        "gefilte", "canned", "pickled", "olive", "tuna", "sardine",
        "tomato paste", "tomato crush",
    ]),
    ("Beverages", [
        "juice", "soda", "water", "drink", "sparkling", "lemonade",
    ]),
    ("Baking & Cooking", [
        "flour", "sugar", "cocoa", "baking", "yeast", "vanilla extract",
        "cooking wine", "oil", "spray", "cornstarch",
    ]),
    ("Soups & Instant", [
        "soup", "broth", "consomme", "instant noodle",
    ]),
    ("Tea & Coffee", [
        "tea", "coffee", "herbal", "chamomile",
    ]),
    ("Cereals & Breakfast", [
        "cereal", "granola", "oatmeal", "muesli",
    ]),
    ("Dairy & Alternatives", [
        "milk", "cheese", "cream cheese", "yogurt", "butter",
    ]),
]


def detect_category(product_name: str) -> str:
    name_lower = product_name.lower().strip()
    for category, keywords in CATEGORIES:
        for kw in keywords:
            if kw in name_lower:
                return category
    return "General Grocery"
