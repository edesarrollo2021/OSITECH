# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
from ..models.tool_convert_numbers_letters import numero_to_letras

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
        'JOSE ', 'JOSÉ', 'J ', 'MARIA ', 'MA. ', 'DE', 'DE ', ' DE ', 'DEL ', ' DEL ', 'LA ', ' LA ',
        'JOSE', 'J', 'MARIA', 'MARÍA', 'MA.', 'DE', ' DEL', 'LA',
        'LAS ', ' LAS ', 'LOS ', ' LOS ', 'MC ', 'MC ', 'MAC ', 'VON ', 'VAN ', ' Y '
        'LAS', 'LOS', 'MC', 'MAC', 'VON', 'VAN',
]

def remove_abbreviation_c(abbreviation):
    abbreviations = ('R.L.','S.C.L.','S.A.','A.C.','C.V.','C.','V.','R.','L.','S.','A.',
                    'COMPAÑÍA','COMPAÑIA', 'CIA.', 'CÍA.', 'SOCIEDAD', 'SOC.'
                    )
    abbr = abbreviation.split()
    data = ''
    for item in abbreviations:
        for i in abbr:
            if i == item:
                abbreviation = abbreviation.replace(i,' ')
            else:
                abbreviation = abbreviation
    data = abbreviation
    return data
    
def cadena_numer_c(name):
    numer = name.split()
    data = name
    for i in numer:
        if i.isdigit() == True:
            name = name.replace(i,numero_to_letras(int(i)))
            data=numero_to_letras(int(i))
        else:
            name = name
    data = name
    return data

def remove_article_c(article):
    "Remove article."
    articles = (
        'DE ','DEL ', 'LA ','LOS ', 'LAS ', 'Y ', 'MC ', 'MAC ', 'VON ', 'VAN ',
        'DE', 'DEL', 'LA','LOS', 'LAS', 'Y', 'MC', 'MAC', 'VON', 'VAN', 'EL', 
        'PARA','.', '. ', ', ',',',
    )
    arti = article.split()
    for item in articles:
        for i in arti:
            if i == item:
                article = article.replace(i,' ')
            else:
                article = article
    data = article
    return data

def remove_signos_c(name):
    "Remove article."
    signos = (
        '.', '. ', ', ',',',':',';','/','*','+','-',
    )
    sig = name.split()
    for item in signos:
        for i in sig:
            if item in i:
                name = name.replace(item, ' ')
            else:
                name = name
    data=name
    return data

def remove_names_c(name):
    "Remove defined names in the tuple."
    for item in NAMES:
        data = name.replace(item, ' ')
    return data
    
def remove_precisions_c(word):
    letters = word[0:2]
    data = word[2:len(word)]
    
    if letters == 'CH':
        word = 'C%s' % data
    elif letters == 'LL':
        word = 'L%s' % data
    return word
    
def complete_name_c(name):
    name = name.lstrip()
    name = name.rstrip()
    data = name
    if len(name) == 2:
        data = '%sX' % name
    elif len(name) == 1:
        data = '%sXX' % name
    return data

def search_consonant(word):
    data = 'X'
    consonant = ''
    length = 0

    if word:
        length = len(word)
        length = length-1
        data = word[1:length]

    for item in data:
        if item == 'Ñ':
            consonant = 'X'
            break
        elif get_consonant(item):
            consonant = item
            break
    return consonant

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

    vocal = ''
    for v in last_name:
        if get_vocal(vocal=v):
            vocal = v
            break
    return vocal

def get_vocal(vocal):
    "Get vocal."
    vowels = ('A', 'E', 'I', 'O', 'U', 'Á', 'É', 'Í', 'Ó', 'Ú')

    for v in vowels:
        if v == vocal:
            return True
            break
    return False
            
def to_upper(text):
    "Convert word to uppercase."
    word = text.upper()
    return word.strip()

