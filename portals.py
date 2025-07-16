# portals.py
# List of major Indian government job portals (central & state)
# You can add/remove portals here. Each portal can have extra config for scraping.

PORTALS = [
    # Central Government
    {"name": "SSC", "url": "https://ssc.nic.in/", "type": "html"},
    {"name": "UPSC", "url": "https://upsc.gov.in/", "type": "html"},
    {"name": "Railway Recruitment Board (RRB)", "url": "https://indianrailways.gov.in/railwayboard/view_section.jsp?lang=0&id=0,4,1244", "type": "html"},
    {"name": "IBPS", "url": "https://www.ibps.in/", "type": "html"},
    {"name": "DRDO", "url": "https://www.drdo.gov.in/careers", "type": "html"},
    {"name": "ISRO", "url": "https://www.isro.gov.in/careers.html", "type": "html"},
    {"name": "Indian Army", "url": "https://joinindianarmy.nic.in/", "type": "html"},
    {"name": "Indian Navy", "url": "https://www.joinindiannavy.gov.in/", "type": "html"},
    {"name": "Indian Air Force", "url": "https://afcat.cdac.in/AFCAT/", "type": "html"},
    # State PSCs (examples, add all states)
    {"name": "Bihar PSC (BPSC)", "url": "https://bpsc.bih.nic.in/", "type": "html"},
    {"name": "UPPSC", "url": "https://uppsc.up.nic.in/", "type": "html"},
    {"name": "MPPSC", "url": "https://mppsc.mp.gov.in/", "type": "html"},
    {"name": "RPSC", "url": "https://rpsc.rajasthan.gov.in/", "type": "html"},
    {"name": "WBPSC", "url": "https://wbpsc.gov.in/", "type": "html"},
    {"name": "HPSC", "url": "http://hpsc.gov.in/", "type": "html"},
    {"name": "JKPSC", "url": "http://jkpsc.nic.in/", "type": "html"},
    {"name": "Kerala PSC", "url": "https://www.keralapsc.gov.in/", "type": "html"},
    {"name": "APPSC", "url": "https://psc.ap.gov.in/", "type": "html"},
    {"name": "TSPSC", "url": "https://www.tspsc.gov.in/", "type": "html"},
    {"name": "UKPSC", "url": "https://psc.uk.gov.in/", "type": "html"},
    {"name": "GPSC (Gujarat)", "url": "https://gpsc.gujarat.gov.in/", "type": "html"},
    {"name": "MPSC (Maharashtra)", "url": "https://mpsc.gov.in/", "type": "html"},
    {"name": "TNPSC", "url": "https://www.tnpsc.gov.in/", "type": "html"},
    {"name": "KPSC (Karnataka)", "url": "https://www.kpsc.kar.nic.in/", "type": "html"},
    # Add all other state PSCs/SSCs/Police/Teacher boards as needed
    # ...
]
