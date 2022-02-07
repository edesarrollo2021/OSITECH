# -*- coding: utf-8 -*-
import datetime
from .utils_company import (
    ENT_FED, WORDS, to_upper, remove_article_c, remove_precisions_c,
    remove_names_c, search_vowel, search_consonant, remove_abbreviation_c,
    complete_name_c, cadena_numer_c, remove_signos_c
)


class BaseGenerator(object):
    """class Base"""
    def generate(self):
        raise NotImplementedError('No implement.')

        
    def parse_company(self, complete_name):
        self.complete_name = to_upper(complete_name)
        self.complete_name = remove_abbreviation_c(self.complete_name)
        # ~ self.complete_name = remove_names_c(self.complete_name)
        self.complete_name = remove_article_c(self.complete_name)
        self.complete_name = remove_signos_c(self.complete_name)
        self.complete_name = remove_precisions_c(self.complete_name)
        self.complete_name = cadena_numer_c(self.complete_name)
        self.complete_name = complete_name_c(self.complete_name)
        
        
        
    def data_fiscal_company(self, complete_name, constitution_date):
        initials = self.initials_name_company(complete_name)
        completename = self.verify_words(initials)
        constitution_date = self.parse_date(constitution_date)
        return '%s%s' % (completename, constitution_date)
        

    def initials_name_company(self, complete_name):
        if len(complete_name.split())==1:
            complete_name=complete_name[0:3]
        elif len(complete_name.split())==2:
            complete_name_cero=complete_name.split()[0][0:1]
            complete_name_uno=complete_name.split()[1][0:2]
            complete_name=complete_name_cero+complete_name_uno
        elif len(complete_name.split())>=3:
            complete_name_cero=complete_name.split()[0][0:1]
            complete_name_uno=complete_name.split()[1][0:1]
            complete_name_dos=complete_name.split()[2][0:1]
            complete_name=complete_name_cero+complete_name_uno+complete_name_dos
        ini_compl_name = complete_name # Initial complete name
        initials = '%s' % (ini_compl_name)
        return initials

    def verify_words(self, rfc):
        for item in WORDS:
            if item == rfc:
                rfc = 'XXXX'
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
        
