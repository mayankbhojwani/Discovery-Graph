import sqlite3
import os

DB_NAME = "curiosity.db"

def get_db_connection(db_path=DB_NAME):
    """Establishes and returns a connection to the SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_db(db_path=DB_NAME):
    """Creates tables for the Curiosity Engine and handles migrations if needed."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Check if the 'realm' column exists in 'nodes' table (migration check)
    try:
        cursor.execute("PRAGMA table_info(nodes)")
        columns = [col[1] for col in cursor.fetchall()]
        if columns and "realm" not in columns:
            # Schema needs update, drop old tables
            cursor.execute("DROP TABLE IF EXISTS edges")
            cursor.execute("DROP TABLE IF EXISTS nodes")
    except Exception:
        pass

    # Create nodes table with realm column
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nodes (
        title TEXT PRIMARY KEY,
        summary TEXT NOT NULL,
        realm TEXT NOT NULL
    )
    """)
    
    # Create edges table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS edges (
        source TEXT,
        target TEXT,
        weight REAL DEFAULT 1.0,
        PRIMARY KEY (source, target),
        FOREIGN KEY (source) REFERENCES nodes (title),
        FOREIGN KEY (target) REFERENCES nodes (title)
    )
    """)
    
    conn.commit()
    conn.close()

def seed_mock_data(db_path=DB_NAME, force=False):
    """Seeds the database with three distinct realms of dense, mock graph data."""
    return  # Disable mock path seeding to focus only on wiki realms
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Check if data already exists to avoid redundant seeding unless forced
    cursor.execute("SELECT COUNT(*) FROM nodes")
    node_count = cursor.fetchone()[0]
    
    if node_count > 0 and not force:
        conn.close()
        return

    # Delete existing records if force seeding
    if force:
        cursor.execute("DELETE FROM edges")
        cursor.execute("DELETE FROM nodes")
        conn.commit()

    # Define the mock datasets for the three realms
    
    # Realm 1: Goan Commerce & Heritage
    goan_nodes = [
        ("Paul John Whisky", "An internationally acclaimed Indian single malt whisky distilled and matured in Goa, capturing the tropical sea breeze in its flavor profile.", "Goan Commerce & Heritage"),
        ("Distilleries", "Goa's alcohol manufacturing industry, which thrives on low excise duties, abundant water resources, and a long tradition of blending and distilling Goan spirits.", "Goan Commerce & Heritage"),
        ("Cashew Feni", "A uniquely Goan spirit distilled from the fermented juice of cashew apples. It is the first Indian liquor to receive a Geographical Indication (GI) tag.", "Goan Commerce & Heritage"),
        ("Heritage Agriculture", "Traditional Goan farming methods focused on hillside cashew orchards, low-lying paddy fields, coconut groves, and multi-crop spice gardens.", "Goan Commerce & Heritage"),
        ("Cazulo Feni Premium", "A pioneering brand dedicated to archiving and bottling premium Goan Cashew and Coconut Feni, operating the world's first heritage feni cellar.", "Goan Commerce & Heritage"),
        ("Mario Miranda Gallery", "Galleries celebrating the life and art of Mario Miranda, the legendary Goan cartoonist whose whimsical illustrations capture traditional Goan village life.", "Goan Commerce & Heritage"),
        ("Loutolim", "A scenic village in Salcete, South Goa, famous for its lush paddy fields, ancestral Portuguese mansions, and rich cultural heritage.", "Goan Commerce & Heritage"),
        ("Portuguese Architecture", "The distinct architectural style of Goa's colonial-era mansions, churches, and public buildings, featuring red-tiled roofs, oyster-shell windows, and grand verandas.", "Goan Commerce & Heritage"),
        ("Heritage Tourism", "Travel centered on exploring Goan history, visiting colonial estates, ancient temples, and heritage sites rather than just commercial beaches.", "Goan Commerce & Heritage"),
        ("Neemrana Three Waters", "A boutique heritage eco-resort in Loutolim, designed around natural springs, creeks, and colonial Portuguese villa aesthetics.", "Goan Commerce & Heritage"),
        ("Kokum (Solkadhi)", "Garcinia indica, a deep-red fruit native to the Western Ghats. Its dried rind (kokum) is a key souring agent in Goan curries and the base of Solkadhi.", "Goan Commerce & Heritage"),
        ("Spice Plantations", "Historic farms in Goa's interior valleys cultivating black pepper, cardamom, vanilla, nutmeg, cashews, and tropical fruits.", "Goan Commerce & Heritage"),
        ("Ponda", "The cultural and spiritual heartland of Goa, surrounded by lush green spice plantations and relocated historic Hindu temples.", "Goan Commerce & Heritage"),
        ("Temples of Goa", "A group of Hindu temples in Ponda, rebuilt during the Inquisition, reflecting a unique fusion of traditional Hindu and colonial Portuguese architecture.", "Goan Commerce & Heritage"),
        ("Mangueshi Temple", "A major 450-year-old temple in Priol, Ponda, dedicated to Lord Manguesh, featuring a landmark seven-storied lamp tower (Deepastambha).", "Goan Commerce & Heritage"),
        ("Cashew Apples", "The fleshy accessory fruit of the cashew tree. Its sweet, astringent juice is stomped and fermented to produce Cashew Feni.", "Goan Commerce & Heritage"),
        ("Coconut Feni", "A traditional Goan spirit distilled from the fermented sap (toddy) collected from the blossoms of coconut palms by local toddy tappers.", "Goan Commerce & Heritage"),
        ("Coconut Palms", "The ubiquitous symbol of the Goan landscape, supplying coconut meat and milk for Goan cuisine and toddy for coconut-based spirits.", "Goan Commerce & Heritage"),
        ("Cazulo Cellars", "The historical cellar in Cansaulim where Cazulo ages its premium feni in hand-blown glass demijohns called 'garrafões' under optimal conditions.", "Goan Commerce & Heritage"),
        ("Ancestral Goa", "An open-air museum and heritage park in Loutolim, showing mock historical Goan village life and housing a giant monolith sculpture of Mirabai.", "Goan Commerce & Heritage"),
        ("Figueiredo House", "A massive heritage mansion in Loutolim, older than the Taj Mahal, showcasing Indo-Portuguese lifestyle and antique furniture.", "Goan Commerce & Heritage"),
        ("Panaji (Panjim)", "The capital city of Goa, located on the banks of the Mandovi River, famous for its Latin Quarter, river cruises, and colonial charm.", "Goan Commerce & Heritage"),
        ("Fontainhas", "The oldest Latin Quarter of Panaji, where narrow streets lined with brightly colored Portuguese houses preserve a strong Mediterranean feel.", "Goan Commerce & Heritage"),
        ("Joseph Bar", "A beloved retro tavern in Fontainhas, popular for serving local draft beers, feni cocktails, and local snacks in a cozy heritage setting.", "Goan Commerce & Heritage"),
        ("Solkadhi", "A traditional pink digestive drink made from kokum extract, coconut milk, garlic, green chilies, and coriander, popular in Goan thalis.", "Goan Commerce & Heritage"),
        ("Goan Fish Curry", "The iconic daily staple of Goa, made with fresh fish cooked in a spicy, tangy coconut gravy flavored with red chilies and sour kokum.", "Goan Commerce & Heritage"),
        ("Savoi Spice Plantation", "A historic 200-year-old organic spice estate in Ponda, pioneer of eco-friendly spice plantation tourism in the region.", "Goan Commerce & Heritage"),
        ("Shanta Durga Temple", "A prominent temple in Kavlem, Ponda, featuring a unique dome-like architecture that blends Hindu, Christian, and Islamic design elements.", "Goan Commerce & Heritage"),
        ("Indo-Portuguese Cuisine", "Goan gastronomy that combines local ingredients (coconut, kokum, rice) with Portuguese techniques and elements (wine vinegar, pork, chilies).", "Goan Commerce & Heritage"),
        ("Feni Cocktails", "Modern mixology creations that use local Cashew or Coconut Feni as a base, mixed with local ingredients like kokum, ginger, and lime.", "Goan Commerce & Heritage"),
        ("Taverns (Copas)", "Traditional local drinking spots in Goan villages where locals gather to drink fresh feni, eat local snacks, and socialize.", "Goan Commerce & Heritage"),
        ("Sahakari Spice Farm", "A large, popular organic farm in Ponda offering guided spice walks, traditional buffet lunches, and elephant bathing experiences.", "Goan Commerce & Heritage"),
        ("Tambdi Surla", "A 12th-century Mahadev temple carved from basalt rock, hidden in the forests of Molem. It is the only surviving pre-Portuguese temple in Goa.", "Goan Commerce & Heritage")
    ]

    # Realm 2: Space Exploration & The Occult
    space_nodes = [
        ("Ancient Astronomy", "The study of celestial bodies by early civilizations, relying on naked-eye observation and philosophical constructs.", "Space Exploration & The Occult"),
        ("Geocentric Model", "A superseded astronomical model in which the Earth is assumed to be at the center of the universe, with all celestial bodies orbiting it.", "Space Exploration & The Occult"),
        ("Copernicus", "Nicolaus Copernicus (1473–1543), the Polish mathematician and astronomer who formulated a model of the universe that placed the Sun rather than the Earth at the center.", "Space Exploration & The Occult"),
        ("Heliocentric Model", "The astronomical model in which the Earth and planets revolve around the Sun at the center of the Universe.", "Space Exploration & The Occult"),
        ("Galileo Galilei", "An Italian astronomer, physicist, and engineer, often called the father of observational astronomy and modern physics. Championed heliocentrism.", "Space Exploration & The Occult"),
        ("Telescope", "An optical instrument designed to make distant objects appear nearer, containing an arrangement of lenses, or of curved mirrors and lenses.", "Space Exploration & The Occult"),
        ("Kepler's Laws", "Three mathematical laws describing the motion of planets around the Sun, published by Johannes Kepler between 1609 and 1619.", "Space Exploration & The Occult"),
        ("Isaac Newton", "An English mathematician and physicist who formulated the laws of motion and universal gravitation, laying the foundations of classical mechanics.", "Space Exploration & The Occult"),
        ("Classical Mechanics", "A physical theory describing the motion of macroscopic objects, from projectiles to machinery and astronomical bodies.", "Space Exploration & The Occult"),
        ("Halley's Comet", "A periodic comet with an orbit of about 75 years, famously predicted by Edmond Halley using Newton's laws of gravitation.", "Space Exploration & The Occult"),
        ("Rocketry", "The science and technology of designing, building, and launching rockets, using reaction propulsion to travel through air and space.", "Space Exploration & The Occult"),
        ("Konstantin Tsiolkovsky", "A Russian and Soviet rocket scientist who pioneered astronautic theory, proposing the rocket equation and space elevator concepts.", "Space Exploration & The Occult"),
        ("Robert Goddard", "An American engineer and physicist who built the world's first liquid-fueled rocket, launched in 1926.", "Space Exploration & The Occult"),
        ("Wernher von Braun", "A German-American aerospace engineer who pioneered rocket technology in Germany (V-2) and later developed the Saturn V rocket for NASA.", "Space Exploration & The Occult"),
        ("V-2 Rocket", "The world's first long-range guided ballistic missile, developed in Germany during World War II, which became the first artificial object to cross the boundary of space.", "Space Exploration & The Occult"),
        ("Cold War", "A period of geopolitical tension between the United States and the Soviet Union and their respective allies, lasting from 1947 to 1991.", "Space Exploration & The Occult"),
        ("Space Race", "A 20th-century competition between two Cold War adversaries, the Soviet Union and the United States, for dominance in spaceflight capability.", "Space Exploration & The Occult"),
        ("Sputnik 1", "The first artificial Earth satellite, launched by the Soviet Union on October 4, 1957, which triggered the Space Race.", "Space Exploration & The Occult"),
        ("Yuri Gagarin", "A Soviet pilot and cosmonaut who became the first human to journey into outer space, completing one orbit of Earth on April 12, 1961.", "Space Exploration & The Occult"),
        ("NASA", "The National Aeronautics and Space Administration, an independent agency of the US federal government responsible for the civil space program.", "Space Exploration & The Occult"),
        ("Project Mercury", "The first human spaceflight program of the United States, running from 1958 through 1963, with the goal of putting a man into Earth orbit.", "Space Exploration & The Occult"),
        ("Apollo Program", "The third United States human spaceflight program carried out by NASA, which succeeded in landing the first humans on the Moon in 1969.", "Space Exploration & The Occult"),
        ("Saturn V", "An American human-rated super heavy-lift launch vehicle used by NASA's Apollo program, designed under the direction of Wernher von Braun.", "Space Exploration & The Occult"),
        ("Apollo 11", "The spaceflight that first landed humans on the Moon on July 20, 1969, carrying commander Neil Armstrong and lunar module pilot Buzz Aldrin.", "Space Exploration & The Occult"),
        ("Moon Landing", "The arrival of a spacecraft on the surface of the Moon. The first manned landing was accomplished by the United States Apollo 11 mission.", "Space Exploration & The Occult"),
        ("Neil Armstrong", "An American astronaut and aeronautical engineer who became the first person to walk on the Moon on July 21, 1969.", "Space Exploration & The Occult"),
        ("Space Shuttle", "A partially reusable low Earth orbital spacecraft system operated by NASA from 1981 to 2011, used for satellite launches and space station construction.", "Space Exploration & The Occult"),
        ("Hubble Space Telescope", "A space telescope launched into low Earth orbit in 1990, providing extremely high-resolution optical images of deep space.", "Space Exploration & The Occult"),
        ("Voyager Program", "An American scientific program that launched two robotic probes, Voyager 1 and Voyager 2, in 1977 to study the outer Solar System and interstellar space.", "Space Exploration & The Occult"),
        ("Golden Record", "Two phonograph records included aboard both Voyager spacecraft, containing sounds and images selected to portray the diversity of life and culture on Earth.", "Space Exploration & The Occult"),
        ("Carl Sagan", "An American astronomer, planetary scientist, and science communicator who co-wrote and narrated the 1980 television series Cosmos.", "Space Exploration & The Occult"),
        ("Cosmos", "A landmark science documentary series presented by Carl Sagan, covering a wide range of scientific subjects, including the origin of life and our place in the universe.", "Space Exploration & The Occult"),
        ("Astrobiology", "An interdisciplinary scientific field concerned with the origins, early evolution, distribution, and future of life in the universe.", "Space Exploration & The Occult"),
        ("Mars Exploration", "The study of Mars by spacecraft, beginning in the late 20th century, seeking to understand its geology, climate, and potential for habitability.", "Space Exploration & The Occult"),
        ("Curiosity Rover", "A car-sized Mars rover designed to explore the Gale Crater on Mars as part of NASA's Mars Science Laboratory mission.", "Space Exploration & The Occult"),
        ("JPL", "The Jet Propulsion Laboratory, a federally funded research and development center managed by Caltech for NASA, specializing in robotic spacecraft exploration.", "Space Exploration & The Occult"),
        ("Exoplanets", "Planets located outside the Solar System, orbiting stars other than the Sun. Their study helps understand planetary formation and astrobiology.", "Space Exploration & The Occult"),
        ("Kepler Space Telescope", "A retired space telescope launched by NASA in 2009 to discover Earth-size planets orbiting other stars, finding thousands of exoplanets.", "Space Exploration & The Occult"),
        ("James Webb Space Telescope", "A space telescope designed primarily to conduct infrared astronomy, acting as the premier space observatory of the 20th and 21st centuries.", "Space Exploration & The Occult"),
        ("Relativity", "Albert Einstein's theory of gravitation and spacetime, encompassing special and general relativity, describing how gravity affects the fabric of space.", "Space Exploration & The Occult"),
        ("Albert Einstein", "A German-born theoretical physicist, widely acknowledged as one of the greatest physicists of all time, who developed the theory of relativity.", "Space Exploration & The Occult"),
        ("Big Bang Theory", "The prevailing cosmological model explaining the expansion of the universe from an extremely hot and dense initial state.", "Space Exploration & The Occult"),
        ("Cosmic Microwave Background", "Electromagnetic radiation relic from an early stage of the universe in Big Bang cosmology, discovered in 1964.", "Space Exploration & The Occult"),
        ("Edwin Hubble", "An American astronomer who proved that many objects previously thought to be nebulae were actually galaxies beyond the Milky Way, and that the universe is expanding.", "Space Exploration & The Occult"),
        ("Andromeda Galaxy", "A spiral galaxy approximately 2.5 million light-years from Earth, and the nearest major galaxy to the Milky Way, famously studied by Edwin Hubble.", "Space Exploration & The Occult"),
        ("Jack Parsons", "An American rocket engineer and occultist, co-founder of the Jet Propulsion Laboratory (JPL), who pioneered solid-fuel rocket technology while practicing esoteric occult rituals.", "Space Exploration & The Occult"),
        ("Occultism", "The study of supernatural, mystical, or magical beliefs and practices, which historically intersected with early scientific investigations (like Newton's alchemy) and early rocketry.", "Space Exploration & The Occult")
    ]

    # Realm 3: Video Game History & Corporate Espionage
    game_nodes = [
        ("Atari", "The pioneer of arcade games and home consoles, founded by Nolan Bushnell, which dominated the early video game industry.", "Video Game History & Corporate Espionage"),
        ("Nolan Bushnell", "Co-founder of Atari, who created Pong and later established the Chuck E. Cheese franchise.", "Video Game History & Corporate Espionage"),
        ("Pong", "The first commercially successful arcade video game, created by Allan Alcorn for Atari, sparking the video game industry.", "Video Game History & Corporate Espionage"),
        ("ET the Extra-Terrestrial", "The infamous Atari 2600 game blamed for the Video Game Crash of 1983, which resulted in millions of unsold cartridges buried in a New Mexico landfill.", "Video Game History & Corporate Espionage"),
        ("Video Game Crash of 1983", "A massive recession in the video game industry caused by market saturation, inflation, and low-quality games like ET.", "Video Game History & Corporate Espionage"),
        ("Nintendo", "The historic Japanese playing card company turned video game giant, which saved the home console industry with the release of the NES.", "Video Game History & Corporate Espionage"),
        ("NES (Nintendo Entertainment System)", "The 8-bit home video game console released by Nintendo in North America in 1985, single-handedly reviving the market.", "Video Game History & Corporate Espionage"),
        ("Gunpei Yokoi", "Nintendo's legendary toy designer and developer of the Game Boy, D-pad, and Metroid, known for lateral thinking.", "Video Game History & Corporate Espionage"),
        ("Hiroshi Yamauchi", "The ruthless, long-time president of Nintendo who transformed the company from hanafuda cards to global video games.", "Video Game History & Corporate Espionage"),
        ("Hanafuda Cards", "Traditional Japanese playing cards, which Nintendo was originally founded to manufacture in Kyoto in 1889.", "Video Game History & Corporate Espionage"),
        ("Yakuza", "Members of transnational organized crime syndicates in Japan, who historically ran illegal gambling parlors using Hanafuda cards.", "Video Game History & Corporate Espionage"),
        ("Kabukicho", "The red-light district of Tokyo, notorious for Yakuza presence, arcade parlors, and underground gambling dens.", "Video Game History & Corporate Espionage"),
        ("Taito", "The Japanese company behind Space Invaders, which sparked the golden age of arcade games in the late 1970s.", "Video Game History & Corporate Espionage"),
        ("Space Invaders", "The landmark 1978 arcade game by Taito that caused a coin shortage in Japan and popularized arcade gaming worldwide.", "Video Game History & Corporate Espionage"),
        ("Namco", "The developer of Pac-Man, which formed a rivalry with Nintendo and Sega in the 1980s.", "Video Game History & Corporate Espionage"),
        ("Pac-Man", "The iconic 1980 arcade game created by Toru Iwatani, which became a global pop culture phenomenon and Namco's mascot.", "Video Game History & Corporate Espionage"),
        ("Sega", "Nintendo's fierce 90s rival, which started as Service Games supplying coin-operated machines to military bases.", "Video Game History & Corporate Espionage"),
        ("Service Games", "The Honolulu-based company that imported slot machines and jukeboxes to Japan, eventually morphing into Sega.", "Video Game History & Corporate Espionage"),
        ("Corporate Espionage", "The practice of spying on competitors to gain a business advantage, which was rampant during the console wars.", "Video Game History & Corporate Espionage"),
        ("Sega Neptune", "An unreleased Sega console whose leaked development secrets became a subject of major corporate espionage and litigation.", "Video Game History & Corporate Espionage"),
        ("Arcade Cabinets", "Large coin-operated machines placed in public spaces, representing the peak of 80s arcade culture and social gaming.", "Video Game History & Corporate Espionage"),
        ("Coin Shortage", "The economic phenomenon in Japan in 1978 caused by the overwhelming popularity of Space Invaders arcade machines.", "Video Game History & Corporate Espionage"),
        ("Super Mario Bros", "The landmark 1985 platform game developed by Shigeru Miyamoto for the NES, which popularized the platformer genre.", "Video Game History & Corporate Espionage"),
        ("Shigeru Miyamoto", "The legendary Nintendo game creator who designed Mario, Zelda, and Donkey Kong, widely considered the father of modern gaming.", "Video Game History & Corporate Espionage"),
        ("Donkey Kong", "The 1981 arcade game that saved Nintendo of America from bankruptcy, introducing Mario (initially named Jumpman).", "Video Game History & Corporate Espionage"),
        ("Nintendo of America", "The US subsidiary of Nintendo, which battled against grey market imports and counterfeit arcade cabinets.", "Video Game History & Corporate Espionage"),
        ("Alpex Computer Corporation", "The company that patented interchangeable game cartridges, which sued Atari and Nintendo for patent infringement.", "Video Game History & Corporate Espionage"),
        ("Grey Market", "The trade of a commodity through distribution channels that are legal but unintended by the original manufacturer.", "Video Game History & Corporate Espionage"),
        ("Tetris", "The Soviet puzzle game created by Alexey Pajitnov, which became the subject of a massive licensing war between Nintendo, Atari, and the KGB.", "Video Game History & Corporate Espionage"),
        ("KGB", "The main security agency for the Soviet Union, which intervened in the licensing rights of Tetris in Moscow.", "Video Game History & Corporate Espionage"),
        ("Alexey Pajitnov", "The Soviet computer engineer who programmed Tetris while working for the Academy of Sciences in Moscow.", "Video Game History & Corporate Espionage"),
        ("Elorg", "The state-owned Soviet organization that controlled the export of software and handled the Tetris licensing war.", "Video Game History & Corporate Espionage"),
        ("Game Boy", "Nintendo's highly successful handheld console, bundled with Tetris, designed by Gunpei Yokoi.", "Video Game History & Corporate Espionage")
    ]

    # Combine all nodes lists
    all_nodes = goan_nodes + space_nodes + game_nodes
    cursor.executemany("INSERT OR REPLACE INTO nodes (title, summary, realm) VALUES (?, ?, ?)", all_nodes)

    # Edge list (directed links representing pathways and bridges)
    edges_data = [
        # --- Realm 1: Goan Commerce & Heritage Edges ---
        ("Paul John Whisky", "Distilleries", 1.0),
        ("Distilleries", "Cashew Feni", 1.0),
        ("Cashew Feni", "Heritage Agriculture", 1.0),
        ("Heritage Agriculture", "Cazulo Feni Premium", 1.0),
        ("Mario Miranda Gallery", "Loutolim", 1.0),
        ("Loutolim", "Portuguese Architecture", 1.0),
        ("Portuguese Architecture", "Heritage Tourism", 1.0),
        ("Heritage Tourism", "Neemrana Three Waters", 1.0),
        ("Kokum (Solkadhi)", "Spice Plantations", 1.0),
        ("Spice Plantations", "Ponda", 1.0),
        ("Ponda", "Temples of Goa", 1.0),
        ("Temples of Goa", "Mangueshi Temple", 1.0),
        ("Distilleries", "Coconut Feni", 1.0),
        ("Coconut Feni", "Coconut Palms", 1.0),
        ("Coconut Palms", "Heritage Agriculture", 1.0),
        ("Cashew Feni", "Cashew Apples", 1.0),
        ("Cashew Apples", "Heritage Agriculture", 1.0),
        ("Cashew Feni", "Cazulo Feni Premium", 1.0),
        ("Cazulo Feni Premium", "Cazulo Cellars", 1.0),
        ("Cazulo Cellars", "Heritage Tourism", 1.0),
        ("Cazulo Feni Premium", "Feni Cocktails", 1.0),
        ("Feni Cocktails", "Joseph Bar", 1.0),
        ("Joseph Bar", "Fontainhas", 1.0),
        ("Fontainhas", "Portuguese Architecture", 1.0),
        ("Mario Miranda Gallery", "Panaji (Panjim)", 1.0),
        ("Panaji (Panjim)", "Fontainhas", 1.0),
        ("Loutolim", "Ancestral Goa", 1.0),
        ("Ancestral Goa", "Heritage Tourism", 1.0),
        ("Loutolim", "Figueiredo House", 1.0),
        ("Figueiredo House", "Portuguese Architecture", 1.0),
        ("Figueiredo House", "Heritage Tourism", 1.0),
        ("Heritage Tourism", "Temples of Goa", 1.0),
        ("Kokum (Solkadhi)", "Solkadhi", 1.0),
        ("Solkadhi", "Indo-Portuguese Cuisine", 1.0),
        ("Indo-Portuguese Cuisine", "Goan Fish Curry", 1.0),
        ("Heritage Agriculture", "Coconut Palms", 1.0),
        ("Heritage Agriculture", "Goan Fish Curry", 1.0),
        ("Heritage Agriculture", "Kokum (Solkadhi)", 1.0),
        ("Spice Plantations", "Savoi Spice Plantation", 1.0),
        ("Savoi Spice Plantation", "Heritage Tourism", 1.0),
        ("Spice Plantations", "Sahakari Spice Farm", 1.0),
        ("Sahakari Spice Farm", "Heritage Tourism", 1.0),
        ("Ponda", "Savoi Spice Plantation", 1.0),
        ("Ponda", "Sahakari Spice Farm", 1.0),
        ("Temples of Goa", "Shanta Durga Temple", 1.0),
        ("Shanta Durga Temple", "Portuguese Architecture", 1.0),
        ("Temples of Goa", "Tambdi Surla", 1.0),
        ("Tambdi Surla", "Heritage Tourism", 1.0),
        ("Mangueshi Temple", "Ponda", 1.0),
        ("Cazulo Cellars", "Taverns (Copas)", 1.0),
        ("Taverns (Copas)", "Joseph Bar", 1.0),
        ("Cashew Feni", "Taverns (Copas)", 1.0),
        ("Feni Cocktails", "Indo-Portuguese Cuisine", 1.0),
        ("Goan Fish Curry", "Indo-Portuguese Cuisine", 1.0),

        # --- Realm 2: Space Exploration & The Occult Edges ---
        ("Ancient Astronomy", "Geocentric Model", 1.0),
        ("Ancient Astronomy", "Copernicus", 1.0),
        ("Geocentric Model", "Copernicus", 1.0),
        ("Geocentric Model", "Galileo Galilei", 1.0),
        ("Copernicus", "Heliocentric Model", 1.0),
        ("Heliocentric Model", "Galileo Galilei", 1.0),
        ("Heliocentric Model", "Kepler's Laws", 1.0),
        ("Galileo Galilei", "Telescope", 1.0),
        ("Galileo Galilei", "Heliocentric Model", 1.0),
        ("Galileo Galilei", "Isaac Newton", 1.0),
        ("Telescope", "Galileo Galilei", 1.0),
        ("Telescope", "Hubble Space Telescope", 1.0),
        ("Telescope", "Kepler Space Telescope", 1.0),
        ("Telescope", "James Webb Space Telescope", 1.0),
        ("Telescope", "Edwin Hubble", 1.0),
        ("Kepler's Laws", "Isaac Newton", 1.0),
        ("Isaac Newton", "Classical Mechanics", 1.0),
        ("Isaac Newton", "Kepler's Laws", 1.0),
        ("Isaac Newton", "Halley's Comet", 1.0),
        ("Isaac Newton", "Albert Einstein", 1.0),
        ("Classical Mechanics", "Isaac Newton", 1.0),
        ("Classical Mechanics", "Relativity", 1.0),
        ("Halley's Comet", "Isaac Newton", 1.0),
        ("Albert Einstein", "Relativity", 1.0),
        ("Albert Einstein", "Big Bang Theory", 1.0),
        ("Relativity", "Albert Einstein", 1.0),
        ("Relativity", "Big Bang Theory", 1.0),
        ("Relativity", "Cosmic Microwave Background", 1.0),
        ("Edwin Hubble", "Telescope", 1.0),
        ("Edwin Hubble", "Big Bang Theory", 1.0),
        ("Edwin Hubble", "Andromeda Galaxy", 1.0),
        ("Big Bang Theory", "Cosmic Microwave Background", 1.0),
        ("Big Bang Theory", "Albert Einstein", 1.0),
        ("Big Bang Theory", "Edwin Hubble", 1.0),
        ("Big Bang Theory", "Carl Sagan", 1.0),
        ("Cosmic Microwave Background", "Big Bang Theory", 1.0),
        ("Andromeda Galaxy", "Edwin Hubble", 1.0),
        ("Space Race", "Cold War", 1.0),
        ("Space Race", "Sputnik 1", 1.0),
        ("Space Race", "Yuri Gagarin", 1.0),
        ("Space Race", "NASA", 1.0),
        ("Space Race", "Apollo Program", 1.0),
        ("Space Race", "Wernher von Braun", 1.0),
        ("Cold War", "Space Race", 1.0),
        ("Cold War", "Sputnik 1", 1.0),
        ("Cold War", "V-2 Rocket", 1.0),
        ("V-2 Rocket", "Wernher von Braun", 1.0),
        ("V-2 Rocket", "Robert Goddard", 1.0),
        ("V-2 Rocket", "Space Race", 1.0),
        ("Wernher von Braun", "V-2 Rocket", 1.0),
        ("Wernher von Braun", "Saturn V", 1.0),
        ("Wernher von Braun", "NASA", 1.0),
        ("Wernher von Braun", "Apollo Program", 1.0),
        ("Robert Goddard", "Rocketry", 1.0),
        ("Robert Goddard", "Konstantin Tsiolkovsky", 1.0),
        ("Robert Goddard", "Wernher von Braun", 1.0),
        ("Konstantin Tsiolkovsky", "Rocketry", 1.0),
        ("Konstantin Tsiolkovsky", "Robert Goddard", 1.0),
        ("Rocketry", "Robert Goddard", 1.0),
        ("Rocketry", "Konstantin Tsiolkovsky", 1.0),
        ("Rocketry", "V-2 Rocket", 1.0),
        ("Rocketry", "Saturn V", 1.0),
        ("Sputnik 1", "Space Race", 1.0),
        ("Sputnik 1", "Yuri Gagarin", 1.0),
        ("Sputnik 1", "Cold War", 1.0),
        ("Yuri Gagarin", "Sputnik 1", 1.0),
        ("Yuri Gagarin", "Space Race", 1.0),
        ("Yuri Gagarin", "Apollo 11", 1.0),
        ("NASA", "Space Race", 1.0),
        ("NASA", "Project Mercury", 1.0),
        ("NASA", "Apollo Program", 1.0),
        ("NASA", "JPL", 1.0),
        ("NASA", "Space Shuttle", 1.0),
        ("NASA", "Hubble Space Telescope", 1.0),
        ("NASA", "Voyager Program", 1.0),
        ("NASA", "Curiosity Rover", 1.0),
        ("Project Mercury", "NASA", 1.0),
        ("Project Mercury", "Space Race", 1.0),
        ("Project Mercury", "Apollo Program", 1.0),
        ("Apollo Program", "NASA", 1.0),
        ("Apollo Program", "Saturn V", 1.0),
        ("Apollo Program", "Apollo 11", 1.0),
        ("Apollo Program", "Moon Landing", 1.0),
        ("Saturn V", "Apollo Program", 1.0),
        ("Saturn V", "Wernher von Braun", 1.0),
        ("Saturn V", "Apollo 11", 1.0),
        ("Apollo 11", "Apollo Program", 1.0),
        ("Apollo 11", "Moon Landing", 1.0),
        ("Apollo 11", "Neil Armstrong", 1.0),
        ("Moon Landing", "Apollo 11", 1.0),
        ("Moon Landing", "Neil Armstrong", 1.0),
        ("Moon Landing", "Cold War", 1.0),
        ("Moon Landing", "Space Race", 1.0),
        ("Neil Armstrong", "Apollo 11", 1.0),
        ("Neil Armstrong", "Moon Landing", 1.0),
        ("Space Shuttle", "NASA", 1.0),
        ("Space Shuttle", "Hubble Space Telescope", 1.0),
        ("Hubble Space Telescope", "NASA", 1.0),
        ("Hubble Space Telescope", "Telescope", 1.0),
        ("Hubble Space Telescope", "Edwin Hubble", 1.0),
        ("Hubble Space Telescope", "James Webb Space Telescope", 1.0),
        ("James Webb Space Telescope", "NASA", 1.0),
        ("James Webb Space Telescope", "Telescope", 1.0),
        ("James Webb Space Telescope", "Hubble Space Telescope", 1.0),
        ("James Webb Space Telescope", "Exoplanets", 1.0),
        ("Voyager Program", "NASA", 1.0),
        ("Voyager Program", "Golden Record", 1.0),
        ("Voyager Program", "Carl Sagan", 1.0),
        ("Voyager Program", "JPL", 1.0),
        ("Golden Record", "Voyager Program", 1.0),
        ("Golden Record", "Carl Sagan", 1.0),
        ("Carl Sagan", "Voyager Program", 1.0),
        ("Carl Sagan", "Golden Record", 1.0),
        ("Carl Sagan", "Cosmos", 1.0),
        ("Carl Sagan", "Astrobiology", 1.0),
        ("Carl Sagan", "NASA", 1.0),
        ("Cosmos", "Carl Sagan", 1.0),
        ("Cosmos", "Astrobiology", 1.0),
        ("Cosmos", "Big Bang Theory", 1.0),
        ("Astrobiology", "Carl Sagan", 1.0),
        ("Astrobiology", "Cosmos", 1.0),
        ("Astrobiology", "Mars Exploration", 1.0),
        ("Astrobiology", "Exoplanets", 1.0),
        ("Mars Exploration", "Curiosity Rover", 1.0),
        ("Mars Exploration", "JPL", 1.0),
        ("Mars Exploration", "Astrobiology", 1.0),
        ("Curiosity Rover", "Mars Exploration", 1.0),
        ("Curiosity Rover", "JPL", 1.0),
        ("Curiosity Rover", "NASA", 1.0),
        ("JPL", "NASA", 1.0),
        ("JPL", "Voyager Program", 1.0),
        ("JPL", "Mars Exploration", 1.0),
        ("JPL", "Curiosity Rover", 1.0),
        ("Exoplanets", "Kepler Space Telescope", 1.0),
        ("Exoplanets", "James Webb Space Telescope", 1.0),
        ("Exoplanets", "Astrobiology", 1.0),
        ("Kepler Space Telescope", "Exoplanets", 1.0),
        ("Kepler Space Telescope", "Telescope", 1.0),
        ("Kepler Space Telescope", "Kepler's Laws", 1.0),
        ("Kepler Space Telescope", "NASA", 1.0),
        ("JPL", "Jack Parsons", 1.0),
        ("Jack Parsons", "JPL", 1.0),
        ("Rocketry", "Jack Parsons", 1.0),
        ("Jack Parsons", "Rocketry", 1.0),
        ("Jack Parsons", "Occultism", 1.0),
        ("Occultism", "Jack Parsons", 1.0),
        ("Isaac Newton", "Occultism", 1.0),
        ("Occultism", "Isaac Newton", 1.0),
        ("Ancient Astronomy", "Occultism", 1.0),
        ("Occultism", "Ancient Astronomy", 1.0),

        # --- Realm 3: Video Game History & Corporate Espionage Edges ---
        ("Atari", "Nolan Bushnell", 1.0),
        ("Atari", "Pong", 1.0),
        ("Atari", "ET the Extra-Terrestrial", 1.0),
        ("Atari", "Video Game Crash of 1983", 1.0),
        ("Nolan Bushnell", "Atari", 1.0),
        ("Pong", "Atari", 1.0),
        ("ET the Extra-Terrestrial", "Video Game Crash of 1983", 1.0),
        ("Video Game Crash of 1983", "Nintendo", 1.0),
        ("Video Game Crash of 1983", "NES (Nintendo Entertainment System)", 1.0),
        ("Video Game Crash of 1983", "Alpex Computer Corporation", 1.0),
        ("Nintendo", "NES (Nintendo Entertainment System)", 1.0),
        ("Nintendo", "Hiroshi Yamauchi", 1.0),
        ("Nintendo", "Gunpei Yokoi", 1.0),
        ("Nintendo", "Hanafuda Cards", 1.0),
        ("Nintendo", "Shigeru Miyamoto", 1.0),
        ("Nintendo", "Nintendo of America", 1.0),
        ("NES (Nintendo Entertainment System)", "Super Mario Bros", 1.0),
        ("NES (Nintendo Entertainment System)", "Nintendo of America", 1.0),
        ("NES (Nintendo Entertainment System)", "Alpex Computer Corporation", 1.0),
        ("Gunpei Yokoi", "Game Boy", 1.0),
        ("Gunpei Yokoi", "Shigeru Miyamoto", 1.0),
        ("Hiroshi Yamauchi", "Nintendo", 1.0),
        ("Hiroshi Yamauchi", "Hanafuda Cards", 1.0),
        ("Hanafuda Cards", "Yakuza", 1.0),
        ("Hanafuda Cards", "Hiroshi Yamauchi", 1.0),
        ("Yakuza", "Kabukicho", 1.0),
        ("Yakuza", "Hanafuda Cards", 1.0),
        ("Kabukicho", "Yakuza", 1.0),
        ("Kabukicho", "Arcade Cabinets", 1.0),
        ("Taito", "Space Invaders", 1.0),
        ("Taito", "Arcade Cabinets", 1.0),
        ("Space Invaders", "Coin Shortage", 1.0),
        ("Space Invaders", "Arcade Cabinets", 1.0),
        ("Coin Shortage", "Space Invaders", 1.0),
        ("Namco", "Pac-Man", 1.0),
        ("Namco", "Arcade Cabinets", 1.0),
        ("Pac-Man", "Namco", 1.0),
        ("Sega", "Service Games", 1.0),
        ("Sega", "Corporate Espionage", 1.0),
        ("Sega", "Sega Neptune", 1.0),
        ("Service Games", "Sega", 1.0),
        ("Corporate Espionage", "Sega Neptune", 1.0),
        ("Corporate Espionage", "Nintendo of America", 1.0),
        ("Sega Neptune", "Corporate Espionage", 1.0),
        ("Shigeru Miyamoto", "Super Mario Bros", 1.0),
        ("Shigeru Miyamoto", "Donkey Kong", 1.0),
        ("Donkey Kong", "Nintendo of America", 1.0),
        ("Donkey Kong", "Shigeru Miyamoto", 1.0),
        ("Nintendo of America", "Grey Market", 1.0),
        ("Nintendo of America", "Tetris", 1.0),
        ("Alpex Computer Corporation", "Nintendo", 1.0),
        ("Alpex Computer Corporation", "Atari", 1.0),
        ("Grey Market", "Nintendo of America", 1.0),
        ("Tetris", "Alexey Pajitnov", 1.0),
        ("Tetris", "KGB", 1.0),
        ("Tetris", "Elorg", 1.0),
        ("Tetris", "Game Boy", 1.0),
        ("KGB", "Elorg", 1.0),
        ("KGB", "Tetris", 1.0),
        ("Alexey Pajitnov", "Tetris", 1.0),
        ("Elorg", "Tetris", 1.0),
        ("Elorg", "KGB", 1.0),
        ("Game Boy", "Gunpei Yokoi", 1.0),
        ("Game Boy", "Tetris", 1.0)
    ]

    cursor.executemany("INSERT OR REPLACE INTO edges (source, target, weight) VALUES (?, ?, ?)", edges_data)
    
    conn.commit()
    conn.close()

def fetch_graph_data(db_path=DB_NAME, realm=None):
    """Queries nodes and edges from the SQLite database, optionally filtered by realm."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    if realm:
        cursor.execute("SELECT title, summary FROM nodes WHERE realm = ?", (realm,))
        nodes = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("""
            SELECT source, target, weight FROM edges 
            WHERE source IN (SELECT title FROM nodes WHERE realm = ?) 
              AND target IN (SELECT title FROM nodes WHERE realm = ?)
        """, (realm, realm))
        edges = [dict(row) for row in cursor.fetchall()]
    else:
        cursor.execute("SELECT title, summary FROM nodes")
        nodes = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT source, target, weight FROM edges")
        edges = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return nodes, edges
