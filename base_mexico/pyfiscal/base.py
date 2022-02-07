# -*- coding: utf-8 -*-

import unicodedata
import datetime
from .utils import (
    ENT_FED, WORDS, to_upper, remove_article, remove_precisions,
    remove_names, search_vowel, search_consonant
)

KEYWORDS = {
    '/': 'X', '-': 'X', '.': 'X', 'ñ': 'X', 'Ñ': 'X',
}

class BaseGenerator(object):
    """class Base"""
    def generate(self):
        raise NotImplementedError('No implement.')

    def parse(self, complete_name, last_name, mother_last_name=None, city=None,
        state_code=None):
        
        if city is not None:
            self.city = to_upper(city)
        if state_code is not None:
            self.state_code = to_upper(state_code)
        if mother_last_name is not None:
            self.mother_last_name = to_upper(mother_last_name)
            self.mother_last_name = remove_article(self.mother_last_name)
            self.mother_last_name = remove_precisions(self.mother_last_name)
        complete_name = to_upper(complete_name)
        self.complete_name = remove_names(complete_name)
        self.complete_name = remove_precisions(self.complete_name)
        self.last_name = to_upper(last_name)
        self.last_name = remove_article(self.last_name)
        self.last_name = remove_precisions(self.last_name)
        
    def data_fiscal(self, complete_name, last_name, mother_last_name, birth_date):
        initials = self.initials_name(complete_name, last_name, mother_last_name)
        completename = self.verify_words(initials)
        birth_date = self.parse_date(birth_date)
        return '%s%s' % (completename, birth_date)

    def remove_accents(self, s):
        trans_tab = dict.fromkeys(map(ord, u'\u0301\u0308'), None)
        if type(s) is str:
            s = u"%s" % s
        return ''.join((c for c in unicodedata.normalize('NFKC', unicodedata.normalize('NFKD', s).translate(trans_tab))))

    def initials_name(self, complete_name, last_name, mother_last_name):
        complete_name = remove_names(complete_name)
        ini_last_name = last_name[0:1] if last_name[0:1] not in KEYWORDS.keys() else KEYWORDS[last_name[0:1]] # Initial last name
        if mother_last_name is None:
            ini_mothlast_name = 'X'
        else:
            ini_mothlast_name = mother_last_name[0:1] if mother_last_name[0:1] not in KEYWORDS.keys() else KEYWORDS[mother_last_name[0:1]] # Initial mother's last name
        ini_compl_name = ''
        last_name_vowel = ''
        if len(last_name) == 1:
            ini_compl_name = complete_name[0:2] if complete_name[0:2] not in KEYWORDS.keys() else KEYWORDS[complete_name[0:2]] # Initial complete name
        else:
            last_name_vowel = search_vowel(last_name) # Find the first vowel of the last name
            ini_compl_name = complete_name[0:1] if complete_name[0:1] not in KEYWORDS.keys() else KEYWORDS[complete_name[0:1]] # Initial complete name
        initials = '%s%s%s%s' % (self.remove_accents(ini_last_name), self.remove_accents(last_name_vowel), 
                                self.remove_accents(ini_mothlast_name), self.remove_accents(ini_compl_name))
        return initials

    def verify_words(self, rfc):
        for item in WORDS:
            if item == rfc:
                rfc = rfc[0:3] + 'X'
                break
        return rfc

    def parse_date(self, fecha):
        try:
            fecha_type = type(fecha)
            if fecha is None:
                fecha = datetime.datetime.today()
            else:
                if not (fecha_type is datetime.datetime or fecha_type is datetime.date):
                    fecha = datetime.datetime.strptime(fecha, '%d-%m-%Y').date()
            
            year = str(fecha.year)
            year = year[2:4]
            month = str(fecha.month).zfill(2) # Fill with zeros to the left.
            day = str(fecha.day).zfill(2)
            birth_date = '%s%s%s' % (year, month, day) 
            return birth_date
        except Exception as exc:
            raise str(exc)

    def city_search(self, name_city):
        data = ''	
        for key, value in ENT_FED.items():
            if key == name_city:
                data = value
        return data

    def get_consonante(self, word):
        return search_consonant(word)

    def get_year(self, str_date):
        """Get year of birth date."""
        try:
            if str_date is None:
                date = datetime.datetime.today()
            else:
                date = datetime.datetime.strptime(str_date, '%d-%m-%Y').date()
            return date.year
        except Exception as exc:
            raise str(exc)

    def current_year(self):
        return datetime.datetime.now().year
        
