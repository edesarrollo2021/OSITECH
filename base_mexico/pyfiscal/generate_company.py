# -*- coding: utf-8 -*-
import unicodedata
import re
from .base_company import BaseGenerator


class GenerateRfcCompany(BaseGenerator):
    key_value = 'rfc'
    DATA_REQUIRED = ('complete_name', 'constitution_date')
    partial_data = None
    
    def __init__(self, **kwargs):
        self.complete_name = kwargs.get('complete_name')
        self.constitution_date = kwargs.get('constitution_date')
        self.parse_company(complete_name=self.complete_name)
        self.partial_data = self.data_fiscal_company(
            complete_name=self.complete_name, constitution_date=self.constitution_date)
        
    def calculate(self):
        
        complete_name =  u"%s" % (self.complete_name)
        rfc = self.partial_data
        hc = self.homoclave(self.partial_data, complete_name)
        rfc += '%s' % hc
        rfc += self.calc_check_digit(rfc)
        # ~ rfc += self.verification_number(rfc)
        return rfc
    
    def remove_accents(self, s):
        trans_tab = dict.fromkeys(map(ord, u'\u0301\u0308'), None)
        if type(s) is str:
            s = u"%s" % s
        return ''.join((c for c in unicodedata.normalize('NFKC', unicodedata.normalize('NFKD', s).translate(trans_tab))))

    _alphabet = u'0123456789ABCDEFGHIJKLMN&OPQRSTUVWXYZ Ñ'   
     
    def calc_check_digit(self,number):
        number = ('   ' + number)[-12:]
        check = sum(self._alphabet.index(n) * (13 - i) for i, n in enumerate(number))
        return self._alphabet[(11 - check) % 11]   
    
    
    def homoclave(self, rfc, complete_name):
        nombre_numero = '0'
        summary = 0 
        div = 0 
        mod = 0

        rfc1 = {
            ' ':00, '&':10, 'A':11, 'B':12, 'C':13, 'D':14, 'E':15, 'F':16,
            'G':17, 'H':18, 'I':19, 'J':21, 'K':22, 'L':23, 'M':24, 'N':25, 'O':26,
            'P':27, 'Q':28, 'R':29, 'S':32, 'T':33, 'U':34, 'V':35, 'W':36, 'X':37,
            'Y':38, 'Z':39, 'Ñ':40, '0':0, '1':1, '2':2, '3':3, '4':4, '5':5, '6':6,
            '7':7, '8':8,'9':9,
        }
        rfc2 = {
            0:'1', 1:'2', 2:'3', 3:'4', 4:'5', 5:'6', 6:'7', 7:'8', 8:'9', 9:'A', 10:'B',
            11:'C', 12:'D', 13:'E', 14:'F', 15:'G', 16:'H', 17:'I', 18:'J', 19:'K',
            20:'L', 21:'M', 22:'N', 23:'P', 24:'Q', 25:'R', 26:'S', 27:'T', 28:'U',
            29:'V', 30:'W', 31:'X', 32:'Y', 33:'Z',
        }

        # Recorrer el nombre y convertir las letras en su valor numérico.
        
        for count in range(0, len(complete_name)):
            letra = self.remove_accents(complete_name[count])
            nombre_numero += self.rfc_set(str(rfc1[letra]),'00')
        # La formula es:
            # El caracter actual multiplicado por diez mas el valor del caracter
            # siguiente y lo anterior multiplicado por el valor del caracter siguiente.
        for count in range(0,len(nombre_numero)-1):
            count2 = count+1
            summary += ((int(nombre_numero[count])*10) + int(nombre_numero[count2])) * int(nombre_numero[count2])
        
        div = summary % 1000
        mod = div % 34
        div = (div-mod)/34
        homoclave = ''
        homoclave += self.rfc_set(rfc2[int(div)], 'Z')
        homoclave += self.rfc_set(rfc2[int(mod)], 'Z')
        return homoclave

    def verification_number(self, rfc):
        suma_numero = 0 
        suma_parcial = 0
        digito = None 

        rfc3 = {
            'A':10, 'B':11, 'C':12, 'D':13, 'E':14, 'F':15, 'G':16, 'H':17, 'I':18,
            'J':19, 'K':20, 'L':21, 'M':22, 'N':23, 'O':25, 'P':26, 'Q':27, 'R':28,
            'S':29, 'T':30, 'U':31, 'V':32, 'W':33, 'X':34, 'Y':35, 'Z':36, '0':0,
            '1':1, '2':2, '3':3, '4':4, '5':5, '6':6, '7':7, '8':8, '9':9, '':24,
            ' ':37,
        }

        for count in range(0,len(rfc)):
            letra = self.remove_accents(rfc[count])
            if rfc3[letra if letra not in ('ñ','Ñ') else 'X']:
                suma_numero = rfc3[letra if letra not in ('ñ','Ñ') else 'X']
                suma_parcial += (suma_numero*(14-(count+1)))

        modulo = suma_parcial % 11
        digito_parcial = (11-modulo)
        
        if modulo == 0:
            digito = '0'
        if digito_parcial == 10:
            digito = 'A'
        else:
            digito = str(digito_parcial)

        return  digito

    def rfc_set(self, a, b):
        if a == b:
            return b
        else:
            return a

    @property
    def data(self):
        return self.calculate()



class GenerateNSS(BaseGenerator):
    """
    class for CalculeNSS

    """
    def __init__(self, nss):
        self.nss = nss

    def is_valid(self):
        validated = len(self.nss)
        if not validated is 11:  # 11 dígitos y subdelegación válida
            return False

        sub_deleg = int(self.nss[0:2])
        year = self.current_year() % 100
        high_date  = int(self.nss[2:4])
        birth_date = int(self.nss[4:6])

        if sub_deleg is not 97:
            if high_date <= year:
                high_date += 100
            if birth_date <= year: 
                birth_date += 100
            if birth_date  >  high_date:
                return False
        return self._is_luhn_valid()

    def _is_luhn_valid(self): #example 4896889802135
        """ Validate an entry with a check digit. """
        num = list(map(int, str(self.nss)))
        return sum(num[::-2] + [sum(divmod(d * 2, 10)) for d in num[-2::-2]]) % 10 == 0

    def _calculate_luhn(self):
        """ Calculation of said digit. """
        num = list(map(int, str(self.nss)))
        check_digit = 10 - sum(num[-2::-2] + [sum(divmod(d * 2, 10)) for d in num[::-2]]) % 10	
        return 0 if check_digit == 10 else check_digit

    @property
    def data(self):
        return self._calculate_luhn()


class GenericGeneration(object): 
    _data = {}

    def __init__(self, **kwargs):
        self._datos = kwargs

    @property
    def data(self):
        for cls in self.generadores:		
            data = cls.DATA_REQUIRED
            kargs = {key: self._datos[key] for key in data}
            gen = cls(**kargs)
            gen.calculate()
            self._data[gen.key_value] = gen.data

        return self._data
