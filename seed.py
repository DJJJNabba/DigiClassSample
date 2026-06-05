"""Seed the DigiClass database with a realistic demonstration dataset.

Running this module directly re-seeds an empty database:

    python seed.py

It is also invoked automatically by the application on first boot when the
database has no users yet. Seeding is idempotent: it does nothing if the
``users`` table is already populated.

Demonstration accounts all share the password defined in ``DEMO_PASSWORD``
(see README). In a real deployment you would remove or rotate these.
"""

import json
import random
import sqlite3
from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash

DEMO_PASSWORD = "Learn2024!"

# Deterministic output so the demo dataset looks the same on every fresh boot.
_RNG = random.Random(20240601)


# ─── People ─────────────────────────────────────────────────────────────────────

ADMINS = [
    ("Dr. Ruth Calloway", "r.calloway@digiclass.edu"),
]

TEACHERS = [
    ("Alex Morgan", "a.morgan@digiclass.edu"),
    ("Sophie Patel", "s.patel@digiclass.edu"),
    ("James Nguyen", "j.nguyen@digiclass.edu"),
    ("Emma Thompson", "e.thompson@digiclass.edu"),
    ("David Okafor", "d.okafor@digiclass.edu"),
]

STUDENTS = [
    ("Hamish Reid", "hamish.reid@student.digiclass.edu"),
    ("Olivia Chen", "olivia.chen@student.digiclass.edu"),
    ("Liam O'Brien", "liam.obrien@student.digiclass.edu"),
    ("Ava Singh", "ava.singh@student.digiclass.edu"),
    ("Noah Williams", "noah.williams@student.digiclass.edu"),
    ("Mia Kowalski", "mia.kowalski@student.digiclass.edu"),
    ("Ethan Brooks", "ethan.brooks@student.digiclass.edu"),
    ("Isla Murphy", "isla.murphy@student.digiclass.edu"),
    ("Lucas Romano", "lucas.romano@student.digiclass.edu"),
    ("Charlotte Day", "charlotte.day@student.digiclass.edu"),
    ("Zara Ahmed", "zara.ahmed@student.digiclass.edu"),
    ("Felix Becker", "felix.becker@student.digiclass.edu"),
]

SUBJECTS = [
    ("Digital Solutions", True),
    ("Mathematics", True),
    ("Biology", True),
    ("Chemistry", True),
    ("Physics", True),
    ("English", True),
    ("History", True),
    ("Geography", True),
    ("Economics", True),
    ("Computer Science", True),
    ("Legal Studies", False),
]


# ─── Authoring helpers ──────────────────────────────────────────────────────────


def q(question, options, correct_idx, explanation):
    """Build a quiz question from a plain option list and the correct index."""
    ids = ["a", "b", "c", "d", "e"]
    answers = [
        {"id": ids[i], "text": text, "correct": i == correct_idx}
        for i, text in enumerate(options)
    ]
    return {"question": question, "answers": answers, "explanation": explanation}


def fc(front, back, card_type="summary", tags=None):
    return {"front": front, "back": back, "type": card_type, "tags": tags or []}


# ─── Quiz content ───────────────────────────────────────────────────────────────

QUIZZES = [
    {
        "subject": "Digital Solutions",
        "topic": "SQL Fundamentals",
        "difficulty": "medium",
        "questions": [
            q("Which SQL clause filters rows after a GROUP BY has been applied?",
              ["WHERE", "HAVING", "FILTER", "LIMIT"], 1,
              "HAVING filters grouped results, whereas WHERE filters rows before grouping."),
            q("What does SQL stand for?",
              ["Structured Query Language", "Simple Query Language",
               "Sequential Query Logic", "Standard Query Library"], 0,
              "SQL stands for Structured Query Language, the standard language for relational databases."),
            q("Which command retrieves data from a table?",
              ["INSERT", "UPDATE", "SELECT", "FETCH"], 2,
              "SELECT queries and retrieves data from one or more tables."),
            q("What is a PRIMARY KEY?",
              ["A key used to encrypt data", "A unique identifier for each row",
               "The first column in any table", "A reference to another table"], 1,
              "A PRIMARY KEY uniquely identifies each record and cannot be NULL."),
            q("Which JOIN returns only rows with a match in both tables?",
              ["LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "FULL OUTER JOIN"], 2,
              "An INNER JOIN returns only rows that have matching values in both tables."),
        ],
    },
    {
        "subject": "Digital Solutions",
        "topic": "Cybersecurity Principles",
        "difficulty": "hard",
        "questions": [
            q("Which attack intercepts communication between two parties?",
              ["SQL Injection", "Man-in-the-Middle", "Denial of Service", "Phishing"], 1,
              "A Man-in-the-Middle attack secretly relays and may alter communication between two parties."),
            q("What does HTTPS use to secure data in transit?",
              ["Base64 encoding", "TLS/SSL encryption", "MD5 hashing", "ZIP compression"], 1,
              "HTTPS uses TLS (or its predecessor SSL) to encrypt data between client and server."),
            q("What is the principle of least privilege?",
              ["Maximum access for efficiency", "Only admins access the system",
               "Minimum access needed for a role", "Simplest possible passwords"], 2,
              "Least privilege limits access rights to only what a role needs, reducing risk."),
            q("Which is the strongest defence against brute-force password attacks?",
              ["Shorter passwords", "Rate limiting and account lockouts",
               "Storing passwords in plain text", "Disabling HTTPS"], 1,
              "Rate limiting and lockouts slow attackers down dramatically, making brute force impractical."),
        ],
    },
    {
        "subject": "Digital Solutions",
        "topic": "User Interface Design",
        "difficulty": "easy",
        "questions": [
            q("What does UX stand for?",
              ["User Exchange", "User Experience", "Universal Export", "Unified XML"], 1,
              "UX stands for User Experience — how a person feels when using a product."),
            q("Which principle keeps interface elements consistent across screens?",
              ["Contrast", "Consistency", "Chaos", "Compression"], 1,
              "Consistency makes interfaces predictable and easier to learn."),
            q("What is 'white space' in design?",
              ["Unused empty space around elements", "A bug in the layout",
               "Text that is hard to read", "A type of font"], 0,
              "White space (negative space) is the empty area that improves readability and focus."),
            q("Why is accessibility important in UI design?",
              ["It is legally optional", "It ensures everyone, including people with disabilities, can use the product",
               "It only matters for mobile apps", "It slows the site down"], 1,
              "Accessible design ensures people of all abilities can use a product effectively."),
        ],
    },
    {
        "subject": "Computer Science",
        "topic": "Recursion in Algorithms",
        "difficulty": "hard",
        "questions": [
            q("What is the base case in a recursive function?",
              ["The first call", "The condition that stops the recursion",
               "The return type", "The recursive call itself"], 1,
              "The base case stops the function calling itself, preventing infinite recursion."),
            q("What happens with no base case?",
              ["Returns None", "Runs exactly twice", "Causes a stack overflow", "Never executes"], 2,
              "Without a base case the function recurses until the call stack is exhausted."),
            q("Which problem is naturally recursive?",
              ["Adding two numbers", "Traversing a tree structure",
               "Printing a single value", "Declaring a variable"], 1,
              "Tree traversal is naturally recursive because each node contains sub-trees."),
            q("What is the time complexity of a naive recursive Fibonacci?",
              ["O(n)", "O(log n)", "O(2^n)", "O(1)"], 2,
              "Naive recursive Fibonacci recomputes subproblems, giving exponential O(2^n) time."),
        ],
    },
    {
        "subject": "Computer Science",
        "topic": "Big-O Notation",
        "difficulty": "medium",
        "questions": [
            q("What does Big-O notation describe?",
              ["Exact runtime in seconds", "How runtime grows with input size",
               "The memory address of data", "The number of bugs"], 1,
              "Big-O describes how an algorithm's cost grows relative to input size."),
            q("Which is fastest for large n?",
              ["O(n^2)", "O(n log n)", "O(n)", "O(log n)"], 3,
              "O(log n) grows slowest, so it is fastest for large inputs."),
            q("Binary search on a sorted array is:",
              ["O(n)", "O(log n)", "O(n^2)", "O(1)"], 1,
              "Binary search halves the search space each step, giving O(log n)."),
            q("A nested loop over the same n-element list is typically:",
              ["O(n)", "O(2n)", "O(n^2)", "O(log n)"], 2,
              "Two nested loops over n elements give roughly n × n = O(n^2)."),
        ],
    },
    {
        "subject": "Mathematics",
        "topic": "Quadratic Equations",
        "difficulty": "medium",
        "questions": [
            q("The quadratic formula solves equations of the form:",
              ["ax + b = 0", "ax² + bx + c = 0", "a/x = b", "aˣ = b"], 1,
              "The quadratic formula solves any equation of the form ax² + bx + c = 0."),
            q("What does the discriminant b² − 4ac tell you?",
              ["The vertex", "The number and type of roots", "The y-intercept", "The gradient"], 1,
              "The discriminant reveals whether roots are real and distinct, repeated, or complex."),
            q("If the discriminant is negative, the roots are:",
              ["Two real roots", "One repeated root", "Two complex roots", "Undefined"], 2,
              "A negative discriminant means no real roots — the two roots are complex conjugates."),
            q("The graph of a quadratic is a:",
              ["Straight line", "Parabola", "Circle", "Hyperbola"], 1,
              "Quadratic functions graph as parabolas."),
        ],
    },
    {
        "subject": "Mathematics",
        "topic": "Probability Basics",
        "difficulty": "easy",
        "questions": [
            q("The probability of a certain event is:",
              ["0", "0.5", "1", "100"], 2,
              "A certain event has probability 1; an impossible event has probability 0."),
            q("Rolling a fair six-sided die, P(rolling a 4) is:",
              ["1/2", "1/3", "1/6", "4/6"], 2,
              "There is one favourable outcome out of six equally likely outcomes: 1/6."),
            q("Two events that cannot happen at the same time are:",
              ["Independent", "Mutually exclusive", "Complementary", "Conditional"], 1,
              "Mutually exclusive events cannot occur simultaneously."),
            q("P(A) + P(not A) equals:",
              ["0", "0.5", "1", "2"], 2,
              "An event and its complement always sum to 1."),
        ],
    },
    {
        "subject": "Biology",
        "topic": "Cell Structure",
        "difficulty": "easy",
        "questions": [
            q("Which organelle is the 'powerhouse of the cell'?",
              ["Nucleus", "Mitochondrion", "Ribosome", "Golgi apparatus"], 1,
              "Mitochondria generate ATP through respiration, powering the cell."),
            q("Where is genetic material stored in a eukaryotic cell?",
              ["Cytoplasm", "Cell membrane", "Nucleus", "Vacuole"], 2,
              "The nucleus houses the cell's DNA."),
            q("Which structure controls what enters and leaves the cell?",
              ["Cell wall", "Cell membrane", "Nucleolus", "Lysosome"], 1,
              "The cell membrane is selectively permeable, regulating transport in and out."),
            q("Ribosomes are responsible for:",
              ["Photosynthesis", "Protein synthesis", "Digestion", "Storage"], 1,
              "Ribosomes assemble amino acids into proteins."),
        ],
    },
    {
        "subject": "Biology",
        "topic": "DNA and Genetics",
        "difficulty": "hard",
        "questions": [
            q("In DNA, adenine always pairs with:",
              ["Cytosine", "Guanine", "Thymine", "Uracil"], 2,
              "Adenine pairs with thymine (A–T); cytosine pairs with guanine (C–G)."),
            q("The process of copying DNA into mRNA is called:",
              ["Translation", "Transcription", "Replication", "Mutation"], 1,
              "Transcription produces mRNA from a DNA template; translation builds proteins from mRNA."),
            q("A section of DNA coding for a protein is a:",
              ["Chromosome", "Gene", "Nucleotide", "Codon"], 1,
              "A gene is a DNA segment that codes for a particular protein or trait."),
            q("How many bases make up a codon?",
              ["One", "Two", "Three", "Four"], 2,
              "A codon is a sequence of three bases that specifies one amino acid."),
        ],
    },
    {
        "subject": "Chemistry",
        "topic": "The Periodic Table",
        "difficulty": "medium",
        "questions": [
            q("Elements in the same group have the same number of:",
              ["Neutrons", "Valence electrons", "Protons", "Isotopes"], 1,
              "Group members share the same number of valence electrons, giving similar properties."),
            q("Which group contains the noble gases?",
              ["Group 1", "Group 7", "Group 18", "Group 2"], 2,
              "Group 18 (the far right column) contains the unreactive noble gases."),
            q("The atomic number of an element equals its number of:",
              ["Neutrons", "Protons", "Electrons + neutrons", "Isotopes"], 1,
              "Atomic number is the number of protons in the nucleus."),
            q("Moving left to right across a period, atomic radius generally:",
              ["Increases", "Decreases", "Stays the same", "Doubles"], 1,
              "Increasing nuclear charge pulls electrons closer, so radius decreases across a period."),
        ],
    },
    {
        "subject": "Chemistry",
        "topic": "Acids and Bases",
        "difficulty": "easy",
        "questions": [
            q("A solution with pH 3 is:",
              ["Strongly basic", "Neutral", "Acidic", "Pure water"], 2,
              "pH below 7 is acidic; pH 3 is a fairly strong acid."),
            q("What does a neutral solution measure on the pH scale?",
              ["0", "7", "14", "1"], 1,
              "pH 7 is neutral — pure water at 25°C."),
            q("Acids release which ion in water?",
              ["OH⁻", "H⁺", "Na⁺", "Cl⁻"], 1,
              "Acids donate hydrogen ions (H⁺) in solution."),
            q("An acid reacting with a base produces salt and:",
              ["Hydrogen gas", "Water", "Oxygen", "Carbon dioxide"], 1,
              "Neutralisation reactions produce a salt and water."),
        ],
    },
    {
        "subject": "Physics",
        "topic": "Newton's Laws of Motion",
        "difficulty": "medium",
        "questions": [
            q("Newton's First Law is also called the law of:",
              ["Acceleration", "Inertia", "Gravity", "Reaction"], 1,
              "The First Law (inertia) states objects keep their motion unless acted on by a net force."),
            q("Newton's Second Law is expressed as:",
              ["E = mc²", "F = ma", "v = u + at", "P = IV"], 1,
              "Force equals mass times acceleration: F = ma."),
            q("For every action there is an equal and opposite:",
              ["Force (reaction)", "Acceleration", "Velocity", "Mass"], 0,
              "Newton's Third Law: every action has an equal and opposite reaction force."),
            q("A net force of zero on an object means it:",
              ["Must be at rest", "Has constant velocity (incl. rest)",
               "Is accelerating", "Has no mass"], 1,
              "Zero net force means zero acceleration — constant velocity, which includes being at rest."),
        ],
    },
    {
        "subject": "Physics",
        "topic": "Energy and Work",
        "difficulty": "hard",
        "questions": [
            q("Work is calculated as:",
              ["Force × distance", "Mass × velocity", "Force ÷ time", "Mass × gravity"], 0,
              "Work = force × distance moved in the direction of the force."),
            q("The SI unit of energy is the:",
              ["Newton", "Watt", "Joule", "Pascal"], 2,
              "Energy and work are measured in joules (J)."),
            q("Gravitational potential energy depends on:",
              ["Mass, gravity and height", "Velocity only", "Temperature", "Charge"], 0,
              "GPE = mgh — mass, gravitational field strength and height."),
            q("Power is the rate of:",
              ["Doing work / transferring energy", "Applying force",
               "Changing mass", "Increasing distance"], 0,
              "Power is energy transferred per unit time (watts = joules per second)."),
        ],
    },
    {
        "subject": "English",
        "topic": "Literary Devices",
        "difficulty": "easy",
        "questions": [
            q("'The wind whispered through the trees' is an example of:",
              ["Simile", "Personification", "Hyperbole", "Onomatopoeia"], 1,
              "Giving human traits ('whispered') to the wind is personification."),
            q("A comparison using 'like' or 'as' is a:",
              ["Metaphor", "Simile", "Allusion", "Pun"], 1,
              "Similes compare using 'like' or 'as'; metaphors compare directly."),
            q("Deliberate exaggeration for effect is:",
              ["Irony", "Hyperbole", "Imagery", "Alliteration"], 1,
              "Hyperbole is exaggeration not meant to be taken literally."),
            q("Repetition of initial consonant sounds is:",
              ["Assonance", "Alliteration", "Rhyme", "Metaphor"], 1,
              "Alliteration repeats initial consonant sounds, e.g. 'silent sea'."),
        ],
    },
    {
        "subject": "History",
        "topic": "World War II",
        "difficulty": "medium",
        "questions": [
            q("In which year did World War II begin in Europe?",
              ["1914", "1939", "1945", "1929"], 1,
              "WWII began in Europe in September 1939 with the invasion of Poland."),
            q("The 1944 Allied invasion of Normandy is known as:",
              ["Operation Barbarossa", "D-Day", "The Blitz", "Pearl Harbor"], 1,
              "D-Day (6 June 1944) was the Allied amphibious invasion of Nazi-occupied France."),
            q("Which event brought the USA into the war in 1941?",
              ["Fall of France", "Attack on Pearl Harbor",
               "Battle of Britain", "Invasion of Poland"], 1,
              "Japan's attack on Pearl Harbor (December 1941) prompted US entry into the war."),
            q("WWII in Europe ended in May 1945 with:",
              ["VE Day", "VJ Day", "The Armistice", "The Treaty of Versailles"], 0,
              "Victory in Europe (VE) Day marked Germany's surrender in May 1945."),
        ],
    },
    {
        "subject": "Economics",
        "topic": "Supply and Demand",
        "difficulty": "medium",
        "questions": [
            q("If demand rises and supply is unchanged, price tends to:",
              ["Fall", "Rise", "Stay the same", "Become zero"], 1,
              "Higher demand against fixed supply pushes the equilibrium price up."),
            q("The law of demand states that, all else equal, as price rises, quantity demanded:",
              ["Rises", "Falls", "Is unchanged", "Doubles"], 1,
              "Higher prices generally reduce the quantity consumers demand."),
            q("The point where supply equals demand is the:",
              ["Surplus", "Shortage", "Equilibrium", "Margin"], 2,
              "Equilibrium is where quantity supplied equals quantity demanded."),
            q("A price set below equilibrium typically causes a:",
              ["Surplus", "Shortage", "Higher price", "No effect"], 1,
              "A binding price ceiling below equilibrium creates a shortage."),
        ],
    },
    {
        "subject": "Geography",
        "topic": "Plate Tectonics",
        "difficulty": "easy",
        "questions": [
            q("Earth's outer shell is broken into moving:",
              ["Layers", "Tectonic plates", "Oceans", "Magnetic fields"], 1,
              "The lithosphere is divided into tectonic plates that move over the mantle."),
            q("Most earthquakes occur at:",
              ["Plate boundaries", "The equator", "Mountain peaks", "River deltas"], 0,
              "Earthquakes concentrate where plates meet and interact."),
            q("Two plates moving apart form a:",
              ["Convergent boundary", "Divergent boundary",
               "Transform boundary", "Subduction zone"], 1,
              "Divergent boundaries occur where plates separate, often forming mid-ocean ridges."),
            q("The driving force behind plate movement is thought to be:",
              ["Tides", "Mantle convection currents", "Wind", "Earth's rotation"], 1,
              "Convection currents in the mantle are believed to drive plate motion."),
        ],
    },
]


# ─── Flashcard content ──────────────────────────────────────────────────────────

FLASHCARD_SETS = [
    {
        "subject": "Digital Solutions",
        "topic": "Caesar Cipher",
        "difficulty": "easy",
        "cards": [
            fc("What is the Caesar Cipher?",
               "A substitution cipher where each letter is shifted a fixed number of positions down the alphabet.",
               "summary", ["definition", "overview"]),
            fc("Who is the Caesar Cipher named after?",
               "Julius Caesar, who used it around 58 BC to protect military messages.",
               "summary", ["history"]),
            fc("How does a shift of 3 encode 'A'?",
               "A → D. Each letter moves three places forward.",
               "detail", ["mechanics", "example"]),
            fc("How is a Caesar Cipher decoded?",
               "Reverse the shift — subtract the key from each letter's position.",
               "detail", ["decryption"]),
            fc("Why is the Caesar Cipher insecure today?",
               "Only 25 possible shifts make it trivial to brute-force; frequency analysis also breaks it.",
               "detail", ["security", "weakness"]),
        ],
    },
    {
        "subject": "Computer Science",
        "topic": "Data Structures",
        "difficulty": "medium",
        "cards": [
            fc("What is a stack?",
               "A Last-In-First-Out (LIFO) collection — the last item added is the first removed.",
               "summary", ["LIFO"]),
            fc("What is a queue?",
               "A First-In-First-Out (FIFO) collection — the first item added is the first removed.",
               "summary", ["FIFO"]),
            fc("What is the key feature of a hash table?",
               "Average O(1) lookup by mapping keys to indices via a hash function.",
               "detail", ["hashing", "performance"]),
            fc("How does a linked list differ from an array?",
               "Elements are linked by pointers rather than stored contiguously, allowing easy insertion/removal.",
               "detail", ["pointers"]),
            fc("What is a binary tree?",
               "A hierarchical structure where each node has at most two children.",
               "summary", ["trees"]),
        ],
    },
    {
        "subject": "Biology",
        "topic": "Photosynthesis",
        "difficulty": "medium",
        "cards": [
            fc("What is photosynthesis?",
               "The process by which plants convert light energy into chemical energy (glucose).",
               "summary", ["definition"]),
            fc("Word equation for photosynthesis?",
               "Carbon dioxide + water → glucose + oxygen (using light energy).",
               "detail", ["equation"]),
            fc("Where does photosynthesis occur?",
               "In the chloroplasts, which contain the pigment chlorophyll.",
               "detail", ["chloroplast"]),
            fc("Why is chlorophyll important?",
               "It absorbs light energy (mainly red and blue) to power the reaction.",
               "summary", ["chlorophyll"]),
            fc("What gas is released as a by-product?",
               "Oxygen.",
               "detail", ["oxygen"]),
        ],
    },
    {
        "subject": "Chemistry",
        "topic": "States of Matter",
        "difficulty": "easy",
        "cards": [
            fc("What are the three common states of matter?",
               "Solid, liquid and gas.",
               "summary", ["states"]),
            fc("What happens to particles when a solid melts?",
               "They gain energy, vibrate more and break free of fixed positions to flow as a liquid.",
               "detail", ["melting"]),
            fc("What is sublimation?",
               "A substance changing directly from solid to gas without becoming liquid.",
               "detail", ["sublimation"]),
            fc("How do gas particles behave?",
               "They move rapidly in all directions and are far apart with negligible forces between them.",
               "summary", ["gas"]),
        ],
    },
    {
        "subject": "Physics",
        "topic": "The Electromagnetic Spectrum",
        "difficulty": "medium",
        "cards": [
            fc("Order the EM spectrum by increasing frequency.",
               "Radio, microwave, infrared, visible, ultraviolet, X-ray, gamma.",
               "detail", ["order"]),
            fc("What do all EM waves have in common?",
               "They are transverse waves that travel at the speed of light in a vacuum.",
               "summary", ["properties"]),
            fc("Which EM waves are used for communication?",
               "Radio waves and microwaves.",
               "detail", ["uses"]),
            fc("Why are gamma rays dangerous?",
               "They have very high frequency and energy and can ionise atoms, damaging cells.",
               "detail", ["safety"]),
        ],
    },
    {
        "subject": "English",
        "topic": "Essay Structure",
        "difficulty": "easy",
        "cards": [
            fc("What does a strong introduction include?",
               "A hook, context, and a clear thesis statement outlining your argument.",
               "summary", ["introduction"]),
            fc("What is the TEEL paragraph structure?",
               "Topic sentence, Evidence, Explanation, Link back to the question.",
               "detail", ["TEEL", "paragraphs"]),
            fc("What is a thesis statement?",
               "A single sentence stating the main argument the essay will prove.",
               "summary", ["thesis"]),
            fc("What belongs in a conclusion?",
               "A restatement of the thesis and a synthesis of key points — no new evidence.",
               "detail", ["conclusion"]),
        ],
    },
    {
        "subject": "Mathematics",
        "topic": "Trigonometry Ratios",
        "difficulty": "medium",
        "cards": [
            fc("What does SOH-CAH-TOA stand for?",
               "Sin = Opposite/Hypotenuse, Cos = Adjacent/Hypotenuse, Tan = Opposite/Adjacent.",
               "summary", ["mnemonic"]),
            fc("In a right triangle, which side is the hypotenuse?",
               "The longest side, opposite the right angle.",
               "detail", ["hypotenuse"]),
            fc("What is sin(30°)?",
               "0.5 — a standard exact value worth memorising.",
               "detail", ["values"]),
            fc("When do you use the sine rule vs the cosine rule?",
               "Sine rule for matched side–angle pairs; cosine rule when you know two sides and the included angle (or all three sides).",
               "summary", ["rules"]),
        ],
    },
    {
        "subject": "Geography",
        "topic": "The Water Cycle",
        "difficulty": "easy",
        "cards": [
            fc("What is evaporation?",
               "Water turning from liquid to vapour, mainly from oceans, driven by the sun.",
               "summary", ["evaporation"]),
            fc("What is condensation?",
               "Water vapour cooling and turning back into liquid droplets, forming clouds.",
               "detail", ["condensation"]),
            fc("What is precipitation?",
               "Water falling from clouds as rain, snow, sleet or hail.",
               "summary", ["precipitation"]),
            fc("What is transpiration?",
               "The release of water vapour from plants through their leaves.",
               "detail", ["plants"]),
        ],
    },
    {
        "subject": "History",
        "topic": "Ancient Rome",
        "difficulty": "medium",
        "cards": [
            fc("When did the Roman Republic become an Empire?",
               "27 BC, when Augustus became the first Roman emperor.",
               "detail", ["timeline"]),
            fc("What was the Roman Senate?",
               "A governing body of elder statesmen that advised leaders and shaped policy.",
               "summary", ["government"]),
            fc("What were Roman roads famous for?",
               "Being straight, durable and enabling fast movement of armies and trade across the empire.",
               "detail", ["engineering"]),
            fc("Why did the Western Roman Empire fall (476 AD)?",
               "A mix of economic decline, military overreach, political instability and invasions.",
               "summary", ["decline"]),
        ],
    },
    {
        "subject": "Economics",
        "topic": "Inflation",
        "difficulty": "medium",
        "cards": [
            fc("What is inflation?",
               "A sustained general rise in the price level, reducing the purchasing power of money.",
               "summary", ["definition"]),
            fc("What is demand-pull inflation?",
               "Inflation caused by demand outpacing supply in the economy.",
               "detail", ["causes"]),
            fc("How is inflation usually measured?",
               "By the Consumer Price Index (CPI), tracking the price of a basket of goods.",
               "detail", ["CPI"]),
            fc("How can central banks reduce inflation?",
               "By raising interest rates to cool spending and borrowing.",
               "summary", ["policy"]),
        ],
    },
]


# ─── Seeding routine ────────────────────────────────────────────────────────────


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def seed_if_empty(db_path: str) -> bool:
    """Seed the database if it has no users. Returns True if seeding ran."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if existing:
            return False
        _seed(conn)
        conn.commit()
        return True
    finally:
        conn.close()


def _seed(conn: sqlite3.Connection) -> None:
    now = datetime.now(timezone.utc)
    pw_hash = generate_password_hash(DEMO_PASSWORD)

    # — Users —
    admin_ids: list[int] = []
    teacher_ids: list[int] = []
    student_ids: list[int] = []

    def add_user(name, email, role, joined_days_ago, bucket):
        created = _iso(now - timedelta(days=joined_days_ago))
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash, role, active, created_at) VALUES (?,?,?,?,1,?)",
            (name, email, pw_hash, role, created),
        )
        bucket.append(cur.lastrowid)

    for name, email in ADMINS:
        add_user(name, email, "admin", 200, admin_ids)
    for name, email in TEACHERS:
        add_user(name, email, "teacher", _RNG.randint(120, 190), teacher_ids)
    for name, email in STUDENTS:
        add_user(name, email, "student", _RNG.randint(20, 110), student_ids)

    # — Subjects —
    subject_ids: dict[str, int] = {}
    for name, active in SUBJECTS:
        cur = conn.execute(
            "INSERT INTO subjects (name, active) VALUES (?, ?)", (name, 1 if active else 0)
        )
        subject_ids[name] = cur.lastrowid

    # — Content items —
    quiz_question_ids: list[tuple[int, list[int]]] = []  # (content_id, [question_id...])

    def reviewer_for() -> int:
        return _RNG.choice(teacher_ids + admin_ids)

    def insert_content(data, content_type):
        subject_id = subject_ids.get(data["subject"])
        created_dt = now - timedelta(
            days=_RNG.randint(1, 75), hours=_RNG.randint(0, 23), minutes=_RNG.randint(0, 59)
        )

        # Distribute statuses realistically: mostly approved, some pending/rejected.
        roll = _RNG.random()
        if roll < 0.72:
            status = "approved"
        elif roll < 0.9:
            status = "pending"
        else:
            status = "rejected"

        # Most published content is authored by teachers; some by keen students.
        if _RNG.random() < 0.8:
            creator = _RNG.choice(teacher_ids)
        else:
            creator = _RNG.choice(student_ids)

        reviewed_by = reviewer_for() if status in ("approved", "rejected") else None
        reviewed_at = (
            _iso(created_dt + timedelta(hours=_RNG.randint(2, 72)))
            if reviewed_by
            else None
        )

        raw = {"topic": data["topic"], "subject": data["subject"], "difficulty": data["difficulty"]}
        if content_type == "quiz":
            raw["questions"] = data["questions"]
        else:
            raw["flashcards"] = data["cards"]

        cur = conn.execute(
            """INSERT INTO content_items
               (created_by, subject_id, topic, difficulty, content_type, status,
                reviewed_by, reviewed_at, created_at, raw_json)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                creator,
                subject_id,
                data["topic"],
                data["difficulty"],
                content_type,
                status,
                reviewed_by,
                reviewed_at,
                _iso(created_dt),
                json.dumps(raw),
            ),
        )
        cid = cur.lastrowid

        if content_type == "quiz":
            qids = []
            for i, question in enumerate(data["questions"]):
                qcur = conn.execute(
                    """INSERT INTO quiz_questions
                       (content_id, question_order, question, options_json, explanation)
                       VALUES (?,?,?,?,?)""",
                    (cid, i, question["question"], json.dumps(question["answers"]), question["explanation"]),
                )
                qids.append(qcur.lastrowid)
            if status == "approved":
                quiz_question_ids.append((cid, qids))
        else:
            for i, card in enumerate(data["cards"]):
                conn.execute(
                    """INSERT INTO flashcards
                       (content_id, card_order, front, back, card_type, tags_json)
                       VALUES (?,?,?,?,?,?)""",
                    (cid, i, card["front"], card["back"], card["type"], json.dumps(card["tags"])),
                )

    for quiz in QUIZZES:
        insert_content(quiz, "quiz")
    for cards in FLASHCARD_SETS:
        insert_content(cards, "flashcard")

    # — User responses (realistic practice history) —
    # Map each approved question to its correct option for grading.
    correct_lookup: dict[int, str] = {}
    for _cid, qids in quiz_question_ids:
        for qid in qids:
            opts = json.loads(
                conn.execute(
                    "SELECT options_json FROM quiz_questions WHERE id = ?", (qid,)
                ).fetchone()["options_json"]
            )
            correct = next((o["id"] for o in opts if o["correct"]), "a")
            correct_lookup[qid] = correct

    for student in student_ids:
        # Each student has a personal aptitude influencing their accuracy.
        aptitude = _RNG.uniform(0.55, 0.92)
        # They attempt a random subset of the approved quizzes.
        attempted = _RNG.sample(
            quiz_question_ids, k=_RNG.randint(2, min(8, len(quiz_question_ids)))
        )
        for _cid, qids in attempted:
            session_dt = now - timedelta(
                days=_RNG.randint(0, 60), hours=_RNG.randint(0, 23), minutes=_RNG.randint(0, 59)
            )
            for offset, qid in enumerate(qids):
                if _RNG.random() > 0.85:
                    continue  # occasionally skip a question
                correct_id = correct_lookup[qid]
                if _RNG.random() < aptitude:
                    selected = correct_id
                    is_correct = 1
                else:
                    wrong = [c for c in ["a", "b", "c", "d"] if c != correct_id]
                    selected = _RNG.choice(wrong)
                    is_correct = 0
                answered = session_dt + timedelta(seconds=offset * _RNG.randint(20, 90))
                conn.execute(
                    """INSERT INTO user_responses
                       (user_id, question_id, selected_option, is_correct, answered_at)
                       VALUES (?,?,?,?,?)""",
                    (student, qid, selected, is_correct, _iso(answered)),
                )


if __name__ == "__main__":
    import os

    path = os.getenv("DATABASE_PATH", "digiclass.db")
    if seed_if_empty(path):
        print(f"Seeded demonstration data into {path!r}.")
        print(f"All demo accounts use the password: {DEMO_PASSWORD}")
    else:
        print(f"Database {path!r} already contains users — nothing to seed.")
