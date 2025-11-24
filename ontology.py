# ontology.py

# 1. The Inventory
# This matches the schema your DataManager expects:
# id, name, owner, safety, capabilities (list)
FAMILY_TOOLS = [
  {
    "id": "POW_01",
    "name": "DEWALT DW130V 9 Amp 1/2-Inch Drill with Spade Handle",
    "owner": "Steven",
    "safety": "Adult Only",
    "capabilities": ["heavy drilling", "mixing applications", "high torque", "corded"]
  },
  {
    "id": "POW_02",
    "name": "DEWALT DCF885C1 20V Max 1/4\" Impact Driver Kit",
    "owner": "Steven",
    "safety": "Adult Only",
    "capabilities": ["driving fasteners", "impact fastening", "cordless", "compact"]
  },
  {
    "id": "AUTO_01",
    "name": "Innovant Adjustable 3 Jaw Oil Filter Wrench Tool",
    "owner": "Steven",
    "safety": "Adult Only",
    "capabilities": ["removing oil filters", "auto maintenance", "mechanical", "universal fit"]
  },
  {
    "id": "AUTO_02",
    "name": "Craftsman 9-45494 Brake Spring Pliers",
    "owner": "Steven",
    "safety": "Adult Only",
    "capabilities": ["brake repair", "drum brakes", "spring removal", "specialty auto"]
  },
  {
    "id": "AUTO_03",
    "name": "BOEN 1/2\" Drive Impact Lug Nut Socket, 7 Pieces Non-Marring",
    "owner": "Steven",
    "safety": "Adult Only",
    "capabilities": ["lug nut removal", "wheel protection", "impact use", "automotive"]
  },
  {
    "id": "ELEC_01",
    "name": "Dual Voltage Tester, Non Contact Tester",
    "owner": "Steven",
    "safety": "Supervised",
    "capabilities": ["voltage detection", "electrical testing", "non-contact", "AC circuit analysis"]
  },
  {
    "id": "ELEC_02",
    "name": "Klein Tools 56331 Fish Tape, Steel Wire Puller",
    "owner": "Steven",
    "safety": "Supervised",
    "capabilities": ["wire pulling", "electrical wiring", "conduit installation", "fishing wire"]
  },
  {
    "id": "CUT_01",
    "name": "DEWALT DW3128P5 80-Tooth 12 in. Crosscutting Saw Blade",
    "owner": "Steven",
    "safety": "Adult Only",
    "capabilities": ["crosscutting", "finish cuts", "miter saw use", "woodworking"]
  },
  {
    "id": "ACC_01",
    "name": "Bosch CCSTV208 8Piece Impact Tough Torx 2 In. Power Bits",
    "owner": "Steven",
    "safety": "Open",
    "capabilities": ["driving torx screws", "impact rated", "fastening", "high torque accessory"]
  },
  {
    "id": "ACC_02",
    "name": "DEWALT DWS2207 7-Piece Premium Percussion Masonry Drill Bit Set",
    "owner": "Steven",
    "safety": "Adult Only",
    "capabilities": ["drilling concrete", "hammer drilling", "masonry work", "high durability"]
  },
  {
    "id": "HAND_01",
    "name": "Scratch Brush Wire Brush for Cleaning Welding Slag",
    "owner": "Family",
    "safety": "Open",
    "capabilities": ["cleaning metal", "rust removal", "welding prep", "manual scrubbing"]
  },
  {
    "id": "PREC_01",
    "name": "Kaisi 126 in 1 Precision Screwdriver Set, SH-111 Bits",
    "owner": "Family",
    "safety": "Supervised",
    "capabilities": ["electronics repair", "precision work", "small screws", "computer maintenance"]
  }
]

# Logic Helper
def check_safety(user_role, tool_safety):
    if user_role == "ADMIN": return True
    if user_role == "ADULT": return True
    if user_role == "CHILD" and tool_safety == "Adult Only": return False
    return True