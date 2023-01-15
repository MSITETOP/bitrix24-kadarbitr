# bitrix24-kadarbitr

<pre>
from bitrix24kadarbitr import KadArbitrDataLoad

kad = KadArbitrDataLoad(
    member_id = 'member_id', 
    placement = "COMPANY",
    entityTypeId = "",
    elementId = 4,  
    client_id = 'app.63...', 
    client_secret = 'client_secret',
    ydb_endpoint = 'grpcs://ydb.serverless.yandexcloud.net:2135',
    ydb_database = '/ru-central1/.....',
    ydb_credentials = 't1.....'
)

oldData = kad.getActualData()
print(oldData)
<pre>
