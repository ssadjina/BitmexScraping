# A collection of functions to scrape bitMEX Trading data
import os
import requests
import gzip
import time
import pandas as pd
from io import StringIO
from tqdm import tqdm


def get_bitmex_data(date, file_dir, endpoint='https://s3-eu-west-1.amazonaws.com/public.bitmex.com/data/trade/{}.csv.gz', leanMode=False, leanModeColumns=['timestamp', 'symbol', 'side', 'size', 'price']):
    '''
    Accesses the BITMEX data in a public AWS bucket* and returns one day.
    'file_dir' specifies where the file is stored.
    'date' specifies which day to use.
    'leanMode' only keeps some of the columns to save memory.
    
    *) 'https://s3-eu-west-1.amazonaws.com/public.bitmex.com/data/trade/{}.csv.gz')
    '''
    
    # Build path to file
    file_path = file_dir + date
    
    # Download file if it does not already exist in the file_path
    if not os.path.isfile(file_path):
        
        count = 0
        
        # Get data from endpoint
        while True:
            r = requests.get(endpoint.format(date))
            if r.status_code == 200:
                break
            else:
                count += 1
                if count == 10:
                    r.raise_for_status()
                print("Error processing {} - {}, trying again".format(date, r.status_code))
                time.sleep(10)
                
        # Write to file
        with open(file_path, 'wb') as fp:
            fp.write(r.content)
    
    # Decode data from zipped file
    with gzip.open(file_path, 'rb') as fp:
        data = fp.read()
        
    # Construct DataFrame
    df = pd.read_csv(
        StringIO(data.decode()),
        header=0,
        usecols=None if not leanMode else leanModeColumns,
        dtype={  # These conversions make sense regardless
            'price': 'float64',  # Looses information if not 64bit
            'symbol': 'category',
            'side': 'category',
            'tickDirection': 'category',
        }
    )
    
    df = df.astype({  # These conversions make sense regardless
        'symbol': 'category',
        'side': 'category',
    })
    
    # Only keep a few columns to save memorey.
    if leanMode:
        #df = df[leanModeColumns]
        
        assert 'size' in df.columns,  'No column \'size\' found!'
        assert (df['size'] >= 0).all(), 'Found negative sizes!'  # All sizes are unsigned
        if df['size'].max() < 2**32:
            df = df.astype({
                'size': 'uint32',
            })
    
    else:
        df['date'] = pd.to_datetime(date)
        
        df = df.astype({
            'homeNotional': 'float64',  # Looses information otherwise
            'foreignNotional': 'float64',  # Looses information otherwise
            'grossValue': 'int64',  # Looses information otherwise
            'tickDirection': 'category',
        })
        
    # Convert timestamps to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='%Y-%m-%dD%H:%M:%S.%f', infer_datetime_format=True)
        
    return df


def get_bitmex_data_period(date_start, date_end, file_dir, leanMode=False):
    '''
    Accesses the BITMEX data in a public AWS bucket* and returns one day.
    'date' specifies which day to use.
    
    *) 'https://s3-eu-west-1.amazonaws.com/public.bitmex.com/data/trade/{}.csv.gz')
    '''
    
    # Set dates
    date = pd.to_datetime(date_start)
    date_end = pd.to_datetime(date_end)
    
    # Set up an empty list to store daily data in
    list_data = []
    
    # Set up progress bar
    pbar = tqdm(total=(date_end - date).days + 1)
    
    # Loop through the days
    while date <= date_end and date <= pd.to_datetime('today'):
        
        date_str = date.strftime('%Y%m%d')
        
        # Get data and append
        list_data.append(
            get_bitmex_data(
                date_str,
                file_dir,
                leanMode=leanMode,
            )
        )
        
        # Advance one day
        date += pd.Timedelta(days=1)
        pbar.update(1)
        
    pbar.close()
        
    # Construct final DataFrame
    df = pd.concat(list_data, ignore_index=True)
    
    # Some last optimiztions
    df = df.astype({
        'symbol': 'category',
        'side': 'category',
    })
    
    return df
