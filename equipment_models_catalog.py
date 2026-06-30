# -*- coding: utf-8 -*-
"""
Catalogue de référence : marques et modèles d’engins (mines, carrières, TP).
Liste non exhaustive mais très étendue (OEM majeurs). Complétez selon vos besoins.
"""

# Libellés complets « marque + famille » — les plus rencontrés sur sites miniers / grandes carrières
TOP_USED_BRAND = "⭐ Les plus utilisés (mines & carrières)"

MODELS_BY_BRAND: dict[str, list[str]] = {
    "Autre / saisie libre": [],
    TOP_USED_BRAND: [
        "Caterpillar 797F",
        "Caterpillar 793F",
        "Caterpillar 789D",
        "Caterpillar 777G",
        "Caterpillar 772G",
        "Caterpillar 992K",
        "Caterpillar 994K",
        "Caterpillar 390F",
        "Caterpillar 395",
        "Caterpillar 349",
        "Caterpillar 336",
        "Caterpillar 330",
        "Caterpillar 320",
        "Caterpillar D10T2",
        "Caterpillar D9",
        "Caterpillar D8T",
        "Komatsu HD785-8",
        "Komatsu HD605-8",
        "Komatsu HD465-8",
        "Komatsu 980E-5",
        "Komatsu 930E-5",
        "Komatsu 830E-5",
        "Komatsu PC4000",
        "Komatsu PC3000",
        "Komatsu PC1250",
        "Komatsu PC850LC",
        "Komatsu PC490LC",
        "Komatsu PC360LC",
        "Komatsu PC290LC",
        "Komatsu PC210LC",
        "Komatsu D475A",
        "Komatsu D375A",
        "Liebherr R996B",
        "Liebherr R980",
        "Liebherr R9600",
        "Liebherr R9350",
        "Liebherr T 284",
        "Liebherr T 264",
        "Liebherr L586",
        "Liebherr L566",
        "Volvo CE A60H",
        "Volvo CE A40G",
        "Volvo CE EC950E",
        "Volvo CE EC750E",
        "Volvo CE EC380E",
        "Volvo CE EC220E",
        "Volvo CE L260H",
        "Hitachi EX5600-6",
        "Hitachi EX3600-6",
        "Hitachi EX1900-6",
        "Hitachi ZX890LCH-6",
        "Hitachi ZX470LC-6",
        "Hitachi EH5000AC-3",
        "BelAZ 75710",
        "BelAZ 75306",
        "Sany SY980H",
        "Sany SY500C",
        "XCMG XDE300",
        "XCMG XE700DF",
    ],
    "BelAZ": [
        "7547", "75473", "7555", "7557", "75131", "75306",
        "789B", "793B", "798B", "75600", "75601", "75710",
        "75151", "75152", "75284", "75285",
    ],
    "Bell": [
        "B20E", "B25E", "B30E", "B35E", "B40E", "B45E", "B50E",
        "B60E", "B18E LGP", "B30D", "B35D", "B40D", "B45D", "B50D",
    ],
    "Bobcat": [
        "E10", "E17", "E19", "E20", "E26", "E27", "E32", "E35", "E40", "E45", "E50", "E55", "E60",
        "L85", "L95", "L110", "L120", "L135", "L150", "L170", "L180", "L200",
        "T450", "T590", "T595", "T62", "T64", "T66", "T76", "T770", "T86",
    ],
    "Case CE": [
        "CX14D", "CX15EVO", "CX25EVO", "CX37C", "CX57C", "CX75C", "CX85D", "CX95D",
        "CX130E", "CX155E", "CX180E", "CX210E", "CX220E", "CX250D", "CX300E", "CX350D",
        "521G", "521G XR", "621G", "721G", "821G", "921G", "1021G", "1121G", "1221G",
        "1650M", "2050M", "2850M",
    ],
    "Caterpillar": [
        # Pelles / excavatrices (sélection large)
        "300.9", "301.5", "301.7", "301.8", "302", "302.7 CR", "303", "303 CR", "303.5", "304", "305", "305.5",
        "306 CR", "307.5", "308", "309 CR", "310", "311", "312", "313 GC", "313", "314", "315", "317", "319",
        "320 GC", "320", "323", "325", "326", "330 GC", "330", "335", "336", "340", "340 UHD", "349", "352",
        "374", "375", "390F", "395",
        "356 Pelle frontale", "6015", "6020B", "6030", "6040", "6050", "6060", "6040 FS",
        "6017", "6020R", "6035",
        # Chargeuses sur pneus
        "901", "906", "907M", "908M", "914", "918", "920", "924K", "924", "926M", "930K", "930M",
        "938K", "938M", "950H", "950M", "950L", "950 GC", "962M", "966M", "972M", "980K", "980M", "982M",
        "986K", "988 GC", "988K", "988 XE", "990K", "992", "992K", "993K", "994K",
        # Tombereaux & tombereaux articulés
        "725", "725C2", "730", "730C2", "735", "735C2", "740 Ejector", "740 GC", "745", "745C",
        "770G", "772G", "773G", "775G", "777D", "777E", "777G", "785D", "785G", "789D", "793D", "793F",
        "794 AC", "796 AC", "797F", "798 AC",
        # Bulldozers
        "D1", "D2", "D3", "D4", "D5", "D6 XE", "D6", "D7E", "D7", "D8T", "D8", "D9", "D9T", "D10T2", "D11",
        # Niveleuses
        "120", "120 GC", "120M2", "140", "140 GC", "140M3", "150", "150 / AWD", "160", "160 AWD", "160M3",
        "16", "16 GC", "18", "18M3", "24", "24M",
        # Autres courants
        "CB13", "CS11 GC", "CP11 GC", "AP255E", "RM500", "PM620", "PM822",
    ],
    "Develon (ex-Doosan)": [
        "DX10Z", "DX17Z", "DX20Z", "DX27Z", "DX35Z", "DX50Z", "DX55R", "DX63-3", "DX85R", "DX100W", "DX140LCR",
        "DX170LC", "DX190W", "DX225LC", "DX235LCR", "DX255LC", "DX300LC", "DX350LC", "DX380LC", "DX420LC",
        "DX490LC", "DX530LC", "DX800LC",
        "DL80", "DL85-5", "DL200-5", "DL220-5", "DL250-5", "DL280-5", "DL300-5", "DL320-5", "DL380-5",
        "DL420-5", "DL480-5", "DL550-5",
        "DA30", "DA40", "DA45-5",
        "DD100", "DD130", "DD140",
    ],
    "Dressta": [
        "TD8S", "TD9S", "TD15M", "TD20M", "TD25M", "TD40",
    ],
    "Epiroc": [
        "SmartROC T35", "SmartROC T40", "SmartROC D60", "SmartROC D65", "DRC10", "DRC16",
        "Pit Viper 235", "Pit Viper 275", "PV 351", "DM45", "DM75",
        "Boomer E1", "Boomer E10", "Boomer M1", "Boomer M2", "Simba E7",
    ],
    "Hitachi": [
        "ZX17U-5", "ZX26U-6", "ZX33U-5", "ZX38U-6", "ZX50U-5", "ZX60USB-5", "ZX85USB-6", "ZX95W-6",
        "ZX130-6", "ZX135US-6", "ZX160LC-6", "ZX180LC-6", "ZX190LC-6", "ZX210LC-6", "ZX225USLC-6", "ZX250LC-6",
        "ZX300LC-6", "ZX350LC-6", "ZX380LC-6", "ZX400LC", "ZX470LC-6", "ZX490LCH-6", "ZX670LC-6", "ZX690LCH-6",
        "ZX890LCH-6", "ZX950LC-6", "ZX1200", "EX1200-7", "EX1900-6", "EX2500-6", "EX2600-6", "EX3600-6",
        "EX5500-6", "EX5600-6", "EX8000-6",
        "EH1100-5", "EH3500ACII", "EH4000ACII", "EH5000AC-3",
        "ZW80-6", "ZW100-6", "ZW120-6", "ZW140-6", "ZW150-6", "ZW180-6", "ZW220-6", "ZW250-6", "ZW310-6",
        "ZW370-6", "ZW550-6",
    ],
    "Hyundai": [
        "HX10A", "HX35Az", "HX40", "HX55", "HX60", "HX85A CR", "HX130A CR", "HX145A CR", "HX160A CR",
        "HX200A", "HX210A", "HX235A CR", "HX260A", "HX300A L", "HX330A L", "HX340A L", "HX400A L",
        "HX480A L", "HX520A L", "HX900S",
        "HL730-9", "HL740-9", "HL757-9", "HL765-9", "HL770-9", "HL780-9", "HL960A", "HL980A",
        "HA30A", "HA45A",
    ],
    "JCB": [
        "8008 CTS", "8010 CTS", "8014", "8018", "8025 ZTS", "8026 CTS", "8030 ZTS", "8035 ZTS", "8040 ZTS",
        "8055 RTS", "8060 RTS", "8065 RTS", "8080", "8085", "8090", "81C-1", "86C-1", "90Z-1", "100C-1", "131X",
        "150X", "155X", "170ZX", "190X", "205X", "220X", "240X", "260X", "300X", "370X",
        "407ZX", "411ZX", "417ZX", "457ZX", "531-70", "533-105", "535-95", "536-95", "541-70", "560-80",
        "HTD-5", "HTD-15",
    ],
    "John Deere": [
        "17G", "26G", "30G", "35G", "50G", "60G", "75G", "85G",
        "130 P-Tier", "210 P-Tier", "250 P-Tier", "300 P-Tier", "350 P-Tier", "470 P-Tier", "670 P-Tier", "870 P-Tier",
        "344L", "444L", "524L", "544L", "624L", "644L", "724L", "744L", "744K-II", "824L", "844L", "944K",
        "1050 P-Tier", "310 P-Tier", "460 P-Tier", "550 P-Tier", "650 P-Tier", "750 P-Tier", "850 P-Tier",
        "764 P-Tier", "824 P-Tier", "872GP", "872GP SmartGrade", "624K-II",
    ],
    "Kobelco": [
        "SK10SR-2", "SK17SR-5", "SK20SR-5", "SK25SR-6", "SK30SR-6", "SK35SR-6", "SK45SRX-6", "SK55SRX-6",
        "SK75UR", "SK85MSR", "SK140SR", "SK170LC", "SK200", "SK210LC", "SK230SR", "SK260LC", "SK300LC",
        "SK350LC", "SK380SRLC", "SK400LC", "SK500LC", "SK550DLC", "SK850LC", "SK1000DLC",
    ],
    "Komatsu": [
        "PC14R", "PC18MR", "PC26MR", "PC30MR", "PC35MR", "PC45MR", "PC55MR", "PC78US", "PC88MR",
        "PC138US", "PC170LC", "PC210LC", "PC228US", "PC240LC", "PC290LC", "PC300LC", "PC360LC", "PC390LC",
        "PC400LC", "PC450LC", "PC490LC", "PC500LC", "PC550LC", "PC600LC", "PC650LC", "PC700LC", "PC750LC",
        "PC800LC", "PC850LC", "PC1250", "PC2000", "PC3000", "PC4000", "PC5500", "PC8000",
        "WA100M", "WA150", "WA200", "WA270", "WA320", "WA380", "WA430", "WA470", "WA480", "WA500", "WA600",
        "WA800", "WA900", "WA1200", "WE1350", "WE1850",
        "HD1500-8", "HD325-8", "HD405-7", "HD465-8", "HD605-8", "HD785-8", "830E-5", "860E-2", "930E-5", "980E-5",
        "D37PX", "D39PX", "D51PX", "D61PX", "D65PX", "D71PX", "D85PX", "D155AX", "D275AX", "D375A", "D475A",
    ],
    "Liebherr": [
        "R914", "R920", "R924", "R926", "R928", "R930", "R934", "R938", "R945", "R954", "R956", "R960", "R964",
        "R966", "R970", "R976", "R980", "R984", "R986", "R990", "R996B",
        "R9100", "R9150", "R9200", "R9250", "R9300", "R9350", "R9400", "R9600",
        "T236", "T264", "T284",
        "L506", "L507", "L508", "L509", "L514", "L524", "L526", "L538", "L550", "L556", "L566", "L580", "L586",
        "PR724", "PR734", "PR744", "PR754", "PR764", "PR776",
        "HS8100", "HS8200", "HS8300", "HS8500", "HS8700", "HS8800",
    ],
    "LiuGong": [
        "9018F", "9027FZ", "9035E", "906E", "908E", "909ECR", "915F", "920F", "922F", "925E", "930E",
        "939E", "948E", "950E", "952E", "965E", "975E", "990F", "9125F", "9135F", "9250E", "970E",
        "816H", "835H", "848H", "856H", "862H", "877H", "890H", "8128H", "8140H",
        "DW90A", "DW105A",
    ],
    "Mecalac": [
        "6MCR", "8MCR", "10MCR", "15MC", "15MC Raupen", "Tank Drum",
        "9MDX", "11MDX",
    ],
    "New Holland": [
        "E10", "E13 SR", "E15", "E17", "E19C", "E21C", "E25 SR", "E30", "E33C", "E39 SR", "E48 SR", "E57 SR",
        "E70 SR", "E80 MSR", "E135 C", "E145 C", "E155 C", "E175 C", "E185 C", "E195 C", "E215 C", "E245 C",
        "W50C", "W60C", "W70C", "W80C", "W110C", "W130C", "W150C", "W170C", "W180C", "W190C",
        "D125", "D150", "D180",
    ],
    "Sany": [
        "SY16C", "SY18U", "SY26U", "SY35U", "SY50U", "SY60C", "SY75C", "SY95C", "SY135C", "SY155C", "SY215C",
        "SY225C", "SY265C", "SY305C", "SY335C", "SY365C", "SY390C", "SY415C", "SY500C", "SY550H", "SY650H",
        "SY750H", "SY870H", "SY980H", "SY1250H", "SET32", "SET70", "SET80", "SET100", "SET150S", "SET230S",
        "SW305", "SW405", "SW956", "SKT90S", "SKT105S", "SAT40C", "SAT50C",
    ],
    "Sandvik": [
        "DR412i", "DR416i", "DR461", "DR480", "D75KX", "D90KS",
        "TH663i", "TH551i", "TH430", "TH320", "LH410", "LH517i", "LH621i", "LH625i",
    ],
    "Schaeff-Terex": [
        "TW110", "TW95", "TC125",
    ],
    "Sumitomo": [
        "SH75X-6B", "SH130-6", "SH135X-6", "SH145-6", "SH160-6", "SH180-6", "SH200-6", "SH210-6", "SH220-6",
        "SH250-6", "SH300-6", "SH350-6", "SH390-6", "SH490-6", "SH530-6",
    ],
    "Takeuchi": [
        "TB210R", "TB215R", "TB220", "TB230", "TB240", "TB250", "TB255", "TB260", "TB285", "TB290",
        "TB325", "TB350", "TB395W",
    ],
    "Terex Trucks": [
        "TA250", "TA300", "TA400", "TR45", "TR50", "TR60", "TR70",
    ],
    "Volvo CE": [
        "EC18E", "EC20E", "EC27D", "EC35D", "EC55D", "EC60E", "EC75D", "EC88MP", "EC120D", "EC140E", "EC160E",
        "EC180E", "EC200E", "EC220E", "EC250E", "EC250E Hybrid", "EC300E", "EC350E", "EC380E", "EC480E", "EC550E",
        "EC750E", "EC950E", "EC950F",
        "L60H", "L70H", "L90H", "L110H", "L120H", "L150H", "L180H", "L220H", "L260H", "L350H",
        "A25G", "A30G", "A35G", "A40G", "A45G", "A60H",
        "SD115B", "SD135B", "P6820D ABG", "P7820D ABG", "PL3005E", "PL4809E",
    ],
    "Wacker Neuson": [
        "EZ17", "EZ26", "EZ30", "EZ36", "EZ50", "WT4", "6003", "6503", "8003", "9503",
    ],
    "XCMG": [
        "XE15U", "XE27U", "XE35U", "XE55U", "XE75DA", "XE135D", "XE155D", "XE215C", "XE225DK", "XE265C",
        "XE335C", "XE370CA", "XE400DK", "XE470D", "XE700DF", "XE950G",
        "LW160FV", "LW180KV", "LW300KN", "LW400KN", "LW500KN", "LW600KN", "LW700KN",
        "XDE40", "XDE110", "XDE200", "XDE240", "XDE300",
    ],
    "Yanmar": [
        "ViO10-2A", "ViO12-2A", "ViO17", "ViO20-3", "ViO26-6", "ViO27-6", "ViO30-6", "ViO33-6", "ViO35-6A",
        "ViO38-6", "ViO50-6A", "ViO57-6A", "ViO80-2", "SV40", "SV60", "SV100-2A", "SV120-7",
    ],
    "Zoomlion": [
        "ZE60E-10", "ZE75E", "ZE135E", "ZE155E", "ZE215E", "ZE245E", "ZE335EK", "ZE370E", "ZE485E", "ZE750EK",
        "ZW120", "ZW150", "ZW180", "ZW220", "ZW250", "ZW330", "ZW370",
    ],
}


# Charge utile indicative (tonnes métriques), sources constructeurs / usages courants — valeur modifiable dans l’UI.
REFERENCE_PAYLOAD_TONNES: dict[str, float] = {
    # ⭐ Liste « les plus utilisés » (libellés complets tels qu’affichés au select)
    "Caterpillar 797F": 400.0,
    "Caterpillar 793F": 241.0,
    "Caterpillar 789D": 181.0,
    "Caterpillar 777G": 98.4,
    "Caterpillar 772G": 52.0,
    "Komatsu HD785-8": 91.0,
    "Komatsu HD605-8": 60.0,
    "Komatsu HD465-8": 55.0,
    "Komatsu 980E-5": 327.0,
    "Komatsu 930E-5": 290.0,
    "Komatsu 830E-5": 222.0,
    "Liebherr T 284": 363.0,
    "Liebherr T 264": 240.0,
    "Volvo CE A60H": 55.0,
    "Volvo CE A40G": 39.0,
    "Hitachi EH5000AC-3": 290.0,
    "BelAZ 75710": 450.0,
    "BelAZ 75306": 220.0,
    "XCMG XDE300": 300.0,
}


def _fill_brand_model_payload_refs() -> None:
    """Complète REFERENCE_PAYLOAD_TONNES avec des clés « Marque|modèle » pour les listes par marque."""
    for brand, models in MODELS_BY_BRAND.items():
        if brand in ("Autre / saisie libre", TOP_USED_BRAND):
            continue
        for m in models:
            key = f"{brand}|{m}"
            if key in REFERENCE_PAYLOAD_TONNES:
                continue
            full = f"{brand} {m}".strip()
            if full in REFERENCE_PAYLOAD_TONNES:
                REFERENCE_PAYLOAD_TONNES[key] = REFERENCE_PAYLOAD_TONNES[full]
                continue
            # Heuristique tombereaux / articulated bien connus (charge utile approx.)
            ml = (m or "").upper()
            if any(
                x in ml
                for x in (
                    "797F",
                    "793F",
                    "793D",
                    "789D",
                    "789C",
                    "785G",
                    "785D",
                    "777G",
                    "775G",
                    "773G",
                    "772G",
                    "770G",
                    "745",
                    "740",
                    "730",
                    "725",
                    "HD785",
                    "HD605",
                    "HD465",
                    "HD405",
                    "HD325",
                    "980E",
                    "930E",
                    "830E",
                    "860E",
                    "EH5000",
                    "EH4000",
                    "EH3500",
                    "T 284",
                    "T284",
                    "T 264",
                    "T264",
                    "T236",
                    "A60H",
                    "A45G",
                    "A40G",
                    "A35G",
                    "A30G",
                    "A25G",
                    "XDE300",
                    "XDE240",
                    "XDE200",
                    "75710",
                    "75306",
                )
            ):
                if "797" in ml or "75710" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 400.0
                elif "793" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 241.0
                elif "789" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 181.0
                elif "785" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 136.0
                elif "777" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 98.4
                elif "775" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 86.0
                elif "773" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 75.0
                elif "772" in ml or "770" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 52.0
                elif "HD785" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 91.0
                elif "HD605" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 60.0
                elif "HD465" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 55.0
                elif "HD405" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 40.0
                elif "HD325" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 32.0
                elif "980E" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 327.0
                elif "930E" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 290.0
                elif "860E" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 254.0
                elif "830E" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 222.0
                elif "EH5000" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 290.0
                elif "EH4000" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 218.0
                elif "EH3500" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 181.0
                elif "T 284" in m or "T284" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 363.0
                elif "T 264" in m or "T264" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 240.0
                elif "T236" in ml or "T 236" in m:
                    REFERENCE_PAYLOAD_TONNES[key] = 224.0
                elif "A60H" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 55.0
                elif "A45G" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 45.0
                elif "A40G" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 39.0
                elif "A35G" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 34.0
                elif "A30G" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 28.0
                elif "A25G" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 22.0
                elif "XDE300" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 300.0
                elif "XDE240" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 220.0
                elif "XDE200" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 180.0
                elif "75306" in ml:
                    REFERENCE_PAYLOAD_TONNES[key] = 220.0


_fill_brand_model_payload_refs()


def get_reference_payload_tonnes(brand: str, model_selected: str, free_text: str = "") -> float | None:
    """
    Retourne une charge utile indicative (t) si le catalogue la connaît, sinon None.
    ``model_selected`` est soit le code modèle (ex: HD785-8), soit le libellé TOP_USED complet.
    """
    b = (brand or "").strip()
    ms = (model_selected or "").strip()
    ft = (free_text or "").strip()

    if b == "Autre / saisie libre":
        if not ft:
            return None
        if ft in REFERENCE_PAYLOAD_TONNES:
            return REFERENCE_PAYLOAD_TONNES[ft]
        for k, v in REFERENCE_PAYLOAD_TONNES.items():
            if "|" not in k and k.upper() in ft.upper():
                return v
        return None

    if b == TOP_USED_BRAND:
        if not ms:
            return None
        return REFERENCE_PAYLOAD_TONNES.get(ms)

    if not ms:
        return None
    k_pipe = f"{b}|{ms}"
    if k_pipe in REFERENCE_PAYLOAD_TONNES:
        return REFERENCE_PAYLOAD_TONNES[k_pipe]
    full = f"{b} {ms}".strip()
    if full in REFERENCE_PAYLOAD_TONNES:
        return REFERENCE_PAYLOAD_TONNES[full]
    if ms in REFERENCE_PAYLOAD_TONNES:
        return REFERENCE_PAYLOAD_TONNES[ms]
    return None


def get_tonnage_preset_values() -> list[float]:
    """Paliers de charge utile courants (t) pour préréglage manuel."""
    base = [30.0, 38.0, 45.0, 52.0, 55.0, 60.0, 75.0, 86.0, 91.0, 98.0, 100.0, 136.0, 181.0, 218.0, 222.0, 240.0, 241.0, 254.0, 290.0, 300.0, 327.0, 363.0, 400.0, 450.0]
    extra = sorted({round(v, 2) for v in REFERENCE_PAYLOAD_TONNES.values() if v > 0})
    merged = sorted({round(x, 2) for x in base + extra})
    return merged


def get_brands_sorted() -> list[str]:
    autre = "Autre / saisie libre"
    keys = list(MODELS_BY_BRAND.keys())
    rest = sorted(k for k in keys if k not in (autre, TOP_USED_BRAND))
    out: list[str] = []
    if autre in MODELS_BY_BRAND:
        out.append(autre)
    if TOP_USED_BRAND in MODELS_BY_BRAND:
        out.append(TOP_USED_BRAND)
    out.extend(rest)
    return out


def get_models_for_brand(brand: str) -> list[str]:
    return list(MODELS_BY_BRAND.get(brand, []))


def format_model_label(brand: str, model: str, free_text: str = "") -> str:
    """Construit le libellé stocké en base."""
    if brand == "Autre / saisie libre":
        return (free_text or "").strip()
    if brand == TOP_USED_BRAND:
        return (model or "").strip()
    if not model:
        return (free_text or "").strip()
    return f"{brand} {model}".strip()


CATALOG_NOTE = (
    "Plus de 850 références courantes (OEM mondiaux). Tout l’inventaire mondial n’est pas numérisable ici — "
    "utilisez « Autre / saisie libre » pour les modèles manquants."
)
