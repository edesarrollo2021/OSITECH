# -*- coding: utf-8 -*-

ENT_FED = { 
    '': '', 'AGUASCALIENTES': 'AS', 'BAJA CALIFORNIA': 'BC', 'BAJA CALIFORNIA SUR': 'BS',
    'CAMPECHE': 'CC', 'CHIAPAS': 'CS', 'CHIHUAHUA': 'CH', 'COAHUILA': 'CL', 'COLIMA': 'CM',
    'CIUDAD DE MÉXICO': 'DF', 'DURANGO': 'DG', 'GUANAJUATO': 'GT', 'GUERRERO': 'GR',
    'HIDALGO': 'HG', 'JALISCO': 'JC', 'MÉXICO': 'MC', 'MICHOACÁN': 'MN', 'MORELOS': 'MS',
    'NAYARIT': 'NT', 'NUEVO LEÓN':'NL', 'OAXACA': 'OC', 'PUEBLA': 'PL', 'QUERÉTARO': 'QT',
    'QUINTANA ROO': 'QR', 'SAN LUIS POTOSÍ': 'SP', 'SINALOA': 'SL', 'SONORA': 'SR',
    'TABASCO': 'TC', 'TAMAULIPAS': 'TS', 'TLAXCALA': 'TL', 'VERACRUZ': 'VZ', 'YUCATÁN': 'YN',
    'ZACATECAS': 'ZS', 'NACIDO EXTRANJERO': 'NE'
}

WORDS = [
    'BUEI', 'BUEY', 'CACA', 'CACO', 'CAGA', 'CAGO', 'CAKA', 'CAKO',
    'COGE', 'COGI', 'COJA', 'COJE', 'COJI', 'COJO', 'COLA', 'CULO',
    'FALO', 'FETO', 'GETA', 'GUEI', 'GUEY', 'JETA', 'JOTO', 'KACA',
    'KACO', 'KAGA', 'KAGO', 'KAKA', 'KAKO', 'KOGE', 'KOGI', 'KOJA',
    'KOJE', 'KOJI', 'KOJO', 'KOLA', 'KULO', 'LILO', 'LOCA', 'LOCO',
    'LOKA', 'LOKO', 'MAME', 'MAMO', 'MEAR', 'MEAS', 'MEON', 'MIAR',
    'MION', 'MOCO', 'MOKO', 'MULA', 'MULO', 'NACA', 'NACO', 'PEDA',
    'PEDO', 'PENE', 'PIPI', 'PITO', 'POPO', 'PUTA', 'PUTO', 'QULO',
    'RATA', 'ROBA', 'ROBE', 'ROBO', 'RUIN', 'SENO', 'TETA', 'VUEI', 
    'VUEY', 'WUEI', 'WUEY'
]

NAMES = [
        'JOSE ', 'JOSÉ', 'J ', 'MARIA ', 'MA. ', 'DE ', ' DE ', 'DEL ', ' DEL ', 'LA ', ' LA ',
        'JOSE', 'J', 'MARIA', 'MARÍA', 'MA.', 'DE', ' DEL', 'LA',
        'LAS ', ' LAS ', 'LOS ', ' LOS ', 'MC ', 'MC ', 'MAC ', 'VON ', 'VAN ', ' Y '
        'LAS', 'LOS', 'MC', 'MAC', 'VON', 'VAN', 'Y'
]

def remove_article(article):
    "Remove article."
    articles = (
        'DE ', 'DEL ', 'LA ','LOS ', 'LAS ', 'Y ', 'MC ', 'MAC ', 'VON ', 'VAN '
        'DE', 'DEL', 'LA','LOS', 'LAS', 'Y', 'MC', 'MAC', 'VON', 'VAN'
    )
    article = article.split()
    data = []
    if len(article) > 1:
        [data.append(n) for n in article if n not in articles]
    else:
        data += article
    # ~ for item in articles:
        # ~ data = article.replace(item, '')
    return data[0]

def remove_names(name):
    "Remove defined names in the tuple."
    name = name.split()
    data = []
    if len(name) > 1:
        for n in name:
            if n in NAMES:
                data.append(name[1])
                break
            else:
                data.append(name[1])
    else:
        data += name
    return data[0]

def remove_precisions(word):
    letters = word[0:2]
    data = word[2:len(word)]
    
    if letters == 'CH':
        word = 'C%s' % data
    elif letters == 'LL':
        word = 'L%s' % data
    return word

def search_consonant(word):
    data = 'X'
    consonant = ''
    length = 0

    if word:
        length = len(word)
        # ~ length = length-1
        data = word[1:length]

    for item in data:
        if item == 'Ñ':
            consonant = 'X'
            break
        elif get_consonant(item):
            consonant = item
            break
        else:
            consonant = 'X'
    return consonant

def remove_signos_c(name):
    "Remove article."
    signos = (
        '.', '. ', ', ',',',':',';','/','*','+','-',
    )
    sig = name.split()
    for item in signos:
        for i in sig:
            if item in i:
                name = name.replace(item, 'X')
            else:
                name = name
    data=name
    return data

def get_consonant(consonant):
    "Get consonant."
    consonants = (
        'B', 'C', 'D', 'F', 'G', 'H', 'J', 'K', 'L', 'M', 'N',
        'P', 'Q', 'R', 'S', 'T', 'V', 'W', 'X', 'Y', 'Z'
    )
    
    for item in consonants:
        if item == consonant:
            return True
            break
    return False

def search_vowel(last_name):
    "Search for paternal surname vowel."
    size = len(last_name) - 1
    last_name = last_name[1:size]
    if not last_name:
        vocal = 'X'
        return vocal

    vocal = ''
    signos = (
        '.', '. ', ', ',',',':',';','/','*','+','-',
    )
    for v in last_name:
        if v in signos:
            vocal = 'X'
            break
        elif get_vocal(vocal=v):
            vocal = v
            break
        else:
            vocal = 'X'
    
    return vocal

def get_vocal(vocal):
    "Get vocal."
    vowels = ('A', 'E', 'I', 'O', 'U', 'Á', 'É', 'Í', 'Ó', 'Ú', 'Ü')

    for v in vowels:
        if v == vocal:
            return True
            break
    return False
            
def to_upper(text):
    "Convert word to uppercase."
    word = text.upper()
    return word.strip()

