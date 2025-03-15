SELECT death_date
FROM person
WHERE death_date NOT REGEXP '^[[:space:]]*[0-9]{4},[[:space:]]*[0-9]{1,2}[[:space:]]+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря|январь|февраль|март|апрель|май|июнь|июль|август|сентябрь|октябрь|ноябрь|декабрь|дкабря|нояб.|агуста|июн)[[:space:]]*$'
    AND death_date NOT REGEXP '^[[:space:]]*[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}[[:space:]]*$'
    AND death_date NOT REGEXP '^[[:space:]]*[0-9]{4}[[:space:]]*г\.\,*[[:space:]]*[0-9]{1,2}[[:space:]]+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря|январь|февраль|март|апрель|май|июнь|июль|август|сентябрь|октябрь|ноябрь|декабрь|дкабря|нояб.|агуста|июн)[[:space:]]*$'

    -- IGNORE
    AND death_date NOT REGEXP '^[0-9]{4}$'

    -- SPECIAL CASES (birth)
    AND death_date NOT REGEXP '^[0-9]{1,2} апр\. [0-9]{4}$' -- 15 апр. 1937
    AND death_date NOT REGEXP '^[0-9]{4}\.[[:space:]][0-9]{1,2} мая$' -- 15 апр. 1937
    AND death_date NOT REGEXP '^[[:space:]]*[0-9]{1,2}-[0-9]{1,2}-[0-9]{4}[[:space:]]*$' -- 23-04-1864
    AND death_date != '1968, 31января '
    AND death_date != '25, ноябрь 1927'
    AND death_date != '1896, 19 февр.'
    AND death_date != '1934. 29 июля'
    AND death_date != '1948, 28 янв.'
    AND death_date != '1939, 2 апреля.'
    AND death_date != '19 ноября 1883 г.'
    AND death_date != '1941, 16.июля'
    AND death_date != '13 сентября 1909'
    AND death_date != '1883 г  3 апреля'
    AND death_date != '1903 г. 26 декабря'
    AND death_date != '1959 25 июня'
    AND death_date != '1915 26 июля'
    AND death_date != '1968, 31января '
    -- SPECIAL CASES (death)
    AND death_date != '1940, 17 феврал'
    AND death_date != '29 июня 1976'
    AND death_date != '1947 , 7 марта'
    AND death_date != '1948 3, мая'
    AND death_date != '1969, 1 мая.'
    AND death_date != '1956 11, сентября'
    AND death_date != '10, марта 2013'
    AND death_date != '2017. 25 июня'
    AND death_date != '19 февраля 1956 г.'
    AND death_date != '14 мая 2006'
    AND death_date != '17 февраля 2005'
    AND death_date != '2004 , 20 августа '
    AND death_date != '1990, 23 августа 199'
    AND death_date != '2005. 15 февраля';