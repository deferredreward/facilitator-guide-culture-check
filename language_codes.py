"""
Language name to ISO 639-1 code mappings for language detection
Supports 100+ languages with common name variations
"""

LANGUAGE_CODES = {
    # Major world languages
    'english': 'en',
    'spanish': 'es', 'castilian': 'es', 'castellano': 'es',
    'french': 'fr', 'français': 'fr',
    'german': 'de', 'deutsch': 'de',
    'italian': 'it', 'italiano': 'it',
    'portuguese': 'pt', 'português': 'pt',
    'russian': 'ru', 'русский': 'ru',
    'chinese': 'zh-cn', 'mandarin': 'zh-cn', '中文': 'zh-cn',
    'japanese': 'ja', '日本語': 'ja',
    'korean': 'ko', '한국어': 'ko',
    'arabic': 'ar', 'العربية': 'ar',
    'hindi': 'hi', 'हिन्दी': 'hi',
    
    # Southeast Asian languages
    'indonesian': 'id', 'bahasa indonesia': 'id',
    'malay': 'ms', 'bahasa malaysia': 'ms', 'bahasa melayu': 'ms',
    'thai': 'th', 'ไทย': 'th',
    'vietnamese': 'vi', 'tiếng việt': 'vi',
    'filipino': 'tl', 'tagalog': 'tl',
    'burmese': 'my', 'myanmar': 'my',
    'khmer': 'km', 'cambodian': 'km',
    'lao': 'lo', 'laotian': 'lo',
    
    # European languages
    'dutch': 'nl', 'nederlands': 'nl',
    'swedish': 'sv', 'svenska': 'sv',
    'norwegian': 'no', 'norsk': 'no',
    'danish': 'da', 'dansk': 'da',
    'finnish': 'fi', 'suomi': 'fi',
    'polish': 'pl', 'polski': 'pl',
    'czech': 'cs', 'čeština': 'cs',
    'slovak': 'sk', 'slovenčina': 'sk',
    'hungarian': 'hu', 'magyar': 'hu',
    'romanian': 'ro', 'română': 'ro',
    'bulgarian': 'bg', 'български': 'bg',
    'croatian': 'hr', 'hrvatski': 'hr',
    'serbian': 'sr', 'српски': 'sr',
    'slovenian': 'sl', 'slovenščina': 'sl',
    'lithuanian': 'lt', 'lietuvių': 'lt',
    'latvian': 'lv', 'latviešu': 'lv',
    'estonian': 'et', 'eesti': 'et',
    'greek': 'el', 'ελληνικά': 'el',
    'turkish': 'tr', 'türkçe': 'tr',
    
    # Middle Eastern languages
    'hebrew': 'he', 'עברית': 'he',
    'persian': 'fa', 'farsi': 'fa', 'فارسی': 'fa',
    'urdu': 'ur', 'اردو': 'ur',
    'kurdish': 'ku', 'کوردی': 'ku',
    
    # African languages
    'swahili': 'sw', 'kiswahili': 'sw',
    'amharic': 'am', 'አማርኛ': 'am',
    'yoruba': 'yo',
    'igbo': 'ig',
    'hausa': 'ha',
    'afrikaans': 'af',
    'zulu': 'zu',
    'xhosa': 'xh',
    'somali': 'so',
    
    # South Asian languages
    'bengali': 'bn', 'বাংলা': 'bn',
    'punjabi': 'pa', 'ਪੰਜਾਬੀ': 'pa',
    'gujarati': 'gu', 'ગુજરાતી': 'gu',
    'marathi': 'mr', 'मराठी': 'mr',
    'tamil': 'ta', 'தமிழ்': 'ta',
    'telugu': 'te', 'తెలుగు': 'te',
    'kannada': 'kn', 'ಕನ್ನಡ': 'kn',
    'malayalam': 'ml', 'മലയാളം': 'ml',
    'nepali': 'ne', 'नेपाली': 'ne',
    'sinhala': 'si', 'සිංහල': 'si',
    
    # East Asian languages
    'mongolian': 'mn', 'монгол': 'mn',
    'tibetan': 'bo', 'བོད་ཡིག': 'bo',
    
    # Latin American languages
    'catalan': 'ca', 'català': 'ca',
    'basque': 'eu', 'euskera': 'eu',
    'galician': 'gl', 'galego': 'gl',
    'quechua': 'qu',
    'guarani': 'gn',
    
    # Pacific languages
    'maori': 'mi',
    'hawaiian': 'haw',
    'samoan': 'sm',
    'tongan': 'to',
    'fijian': 'fj',
    
    # Other European minority languages
    'welsh': 'cy', 'cymraeg': 'cy',
    'irish': 'ga', 'gaeilge': 'ga',
    'scottish gaelic': 'gd', 'gàidhlig': 'gd',
    'breton': 'br',
    'corsican': 'co',
    'maltese': 'mt',
    'icelandic': 'is', 'íslenska': 'is',
    'faroese': 'fo',
    
    # Central Asian languages
    'kazakh': 'kk', 'қазақша': 'kk',
    'kyrgyz': 'ky', 'кыргызча': 'ky',
    'tajik': 'tg', 'тоҷикӣ': 'tg',
    'turkmen': 'tk',
    'uzbek': 'uz', 'oʻzbekcha': 'uz',
    'azerbaijani': 'az', 'azərbaycan': 'az',
    'georgian': 'ka', 'ქართული': 'ka',
    'armenian': 'hy', 'հայերեն': 'hy',
    
    # Additional languages
    'esperanto': 'eo',
    'latin': 'la',
    'sanskrit': 'sa',
    'yiddish': 'yi',
    'frisian': 'fy',
    'luxembourgish': 'lb',
    'albanian': 'sq', 'shqip': 'sq',
    'macedonian': 'mk', 'македонски': 'mk',
    'bosnian': 'bs', 'bosanski': 'bs',
    'montenegrin': 'cnr',
    'belarusian': 'be', 'беларуская': 'be',
    'ukrainian': 'uk', 'українська': 'uk',
    
    # Additional African languages
    'akan': 'ak',
    'ewe': 'ee',
    'twi': 'tw',
    'fula': 'ff',
    'wolof': 'wo',
    'bambara': 'bm',
    'lingala': 'ln',
    'kinyarwanda': 'rw',
    'kirundi': 'rn',
    'luganda': 'lg',
    'shona': 'sn',
    'ndebele': 'nd',
    'sesotho': 'st',
    'setswana': 'tn',
    'chichewa': 'ny',
}

def get_language_code(language_name):
    """
    Convert language name to ISO 639-1 code for langdetect
    
    Args:
        language_name (str): Language name (case insensitive)
        
    Returns:
        str: ISO language code or original input if not found
    """
    if not language_name:
        return ''
    
    # Try exact match first (case insensitive)
    code = LANGUAGE_CODES.get(language_name.lower())
    if code:
        return code
    
    # Try partial matches for compound names
    lower_name = language_name.lower()
    for name, code in LANGUAGE_CODES.items():
        if lower_name in name or name in lower_name:
            return code
    
    # If no match found, return original (might already be a code)
    return language_name.lower()

def get_supported_languages():
    """Get list of all supported language names"""
    return sorted(set(LANGUAGE_CODES.keys()))

def is_language_supported(language_name):
    """Check if a language is supported"""
    return language_name.lower() in LANGUAGE_CODES