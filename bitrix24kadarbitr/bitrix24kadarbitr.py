import ydb
import time  
import requests
import json
import re
import logging
from crestapp import CRestApp

class KadArbitrDataLoad:
    def __init__(self, member_id = '', placement = '',  entityTypeId = '', elementId = '', client_id = '', client_secret = '', ydb_session = False):  
        self.member_id = member_id
        self.bx_id = str(placement)+''+str(entityTypeId)+'_'+str(elementId)
        self.placement = placement
        self.entityTypeId = entityTypeId
        self.elementId =elementId
        self.track = False

        self.__session = ydb_session

        self.__bx24 = CRestApp(
            member_id = member_id, 
            client_id = client_id, 
            client_secret = client_secret, 
            ydb_session = ydb_session
        )

    def __setAppSettings(self, jsonKAD = "", search = "", track = False):
        try:
          if jsonKAD == None: 
            jsonKAD = "null"
          if search == None: 
            search = "null"  
            
          logging.info("__setAppSettings: jsonKAD ={jsonKAD}, search = {search}".format(jsonKAD=jsonKAD, search=search))   
         
          if self.track == True:
            track = True

          query = """
          DECLARE $member_id AS Utf8;
          DECLARE $bx_id AS Utf8;
          DECLARE $jsonKAD AS Json;
          DECLARE $search AS Utf8;
          DECLARE $timestamp AS Timestamp;
          DECLARE $track AS Bool;
          UPSERT INTO `change_tracking`  ( `member_id`, `bx_id`, `jsonKAD`, `search`, `track`,`timestamp` ) VALUES ( $member_id, $bx_id, $jsonKAD, $search, $track, $timestamp );
          """
          prepared_values = {
              '$member_id': self.member_id,
              '$bx_id': self.bx_id,
              '$jsonKAD': jsonKAD,
              '$search': search,
              '$track': track,
              '$timestamp': int(time.time()*1000000), 
          }

          prepared_query = self.__session.prepare(query)

          self.__session.transaction(ydb.SerializableReadWrite()).execute( prepared_query, prepared_values, commit_tx=True )
          return True
        except:
          return False

    def __getAppSettings(self):
        try:
          query = 'DECLARE $member_id AS Utf8; DECLARE $bx_id AS Utf8; SELECT * FROM `change_tracking`  WHERE `member_id` = $member_id AND `bx_id` = $bx_id;'
          prepared_query = self.__session.prepare(query)
          res = self.__session.transaction(ydb.SerializableReadWrite()).execute( prepared_query, { '$member_id': self.member_id, '$bx_id': self.bx_id }, commit_tx=True )   
          settings = res[0].rows[0]
          
          self.jsonKAD = settings.get("jsonKAD")
          self.search = settings.get("search")
          self.track = settings.get("track")

          if settings.get("timestamp"):
            self.timestamp = settings.get("timestamp")
          else:
            self.timestamp = 0
          return True
        except:
          return False

    def getSearch(self, kad_search: str): 
        # kad_search = "А60-7141/2018, А60-27758/2019,А60-6450/2021 А60-12296/2014"
        url = 'https://m.kad.arbitr.ru/Kad/Search'
        data = {
            "Count" : 100, 
            "Courts" : [],
            "Judges" : [],
            "Page" : 1
        }      

        cases = re.findall('А[0-9]+\-[0-9]+\/[0-9]+', kad_search)

        if len(cases):
          data["CaseNumbers"] = cases
          data["Cases"] = cases
        else:
          data["Sides"] = [{"Name" : kad_search, "Type" : -1}]

        headers = {
            'Accept': '*/*',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Host': 'kad.arbitr.ru',
            'Cookie': 'pr_fp=f3110cb19f44e051e916916e1f52a37b09330eb78ac3e59b94c5b6b4ffe27353;', 
            'Origin': 'https://kad.arbitr.ru',
            'Referer': 'https://kad.arbitr.ru/',
            'X-Requested-With': 'XMLHttpRequest'
        }

        r = requests.post(
            url,
            json=data,
            verify=False,
            timeout=10,
            headers=headers
        )

        if r.status_code == 200:
          return {
            'code': r.status_code,
            'text': r.text,
            'json': r.json()
          }
        else:
          return {
            'code': r.status_code,
          }

    def getOldData(self): 
        if self.__getAppSettings():
          return json.loads(self.jsonKAD)
        else:
          return False

    def __compare(self, data: dict = {}): 
        if self.placement=="DYNAMIC":
          msgList = ["[URL=/crm/type/{entityTypeId}/details/{elementId}/] $result[get_crm][item][title] [/URL]".format(entityTypeId=self.entityTypeId, elementId=self.elementId) ]
        else:
          msgList = ["[URL=/crm/{placement}/details/{elementId}/] $result[get_crm][item][title] [/URL]".format(placement=self.placement.lower(), elementId=self.elementId) ]
        
        if self.jsonKAD:
          oldItems = json.loads(self.jsonKAD).get("Result").get("Items")
          newItems = data.get("Result").get("Items")

          oldCases = {}
          for item in oldItems: 
            oldCases[item.get('CaseId')] = item

          newCases = {}
          for item in newItems: 
            newCases[item.get('CaseId')] = item
            if oldCases.get(item.get('CaseId')): # нашли такое дело
              if item.get('IsFinished') ==  True and item.get('IsFinished') != oldCases.get(item.get('CaseId')).get("IsFinished"):
                msgList.append("Рассмотрение дела [URL=https://kad.arbitr.ru/Card/{CaseId}]{CaseNumber}[/URL] завершено".format(CaseId=item.get('CaseId'), CaseNumber=item.get('CaseNumber')))

              if item.get('LastDocumentDate') and item.get('LastDocumentDate') != oldCases.get(item.get('CaseId')).get("LastDocumentDate"):
                casetime = time.strftime("%d.%m.%Y", time.localtime(int(item.get('LastDocumentDate')[6:16])))
                msgList.append("По делу [URL=https://kad.arbitr.ru/Card/{CaseId}]{CaseNumber}[/URL] {LastDocumentDate}  были загружены новые документы".format(CaseId=item.get('CaseId'), CaseNumber=item.get('CaseNumber'), LastDocumentDate=casetime))

            else: # новое дело
              msgList.append("Появилось новое дело: [URL=https://kad.arbitr.ru/Card/{CaseId}]{CaseNumber}[/URL]".format(CaseId=item.get('CaseId'), CaseNumber=item.get('CaseNumber')))

          if len(msgList)>1:
            logging.info("Send to b24: {msgList}".format(msgList=msgList))
            self.__callBatch(msgList)

          return True
        else:
          return False

    def __getEntityTypeCodeToId(self, placement):
        entityTypeCodeToId = {
            "LEAD": 1,
            "DEAL": 2,
            "CONTACT": 3,
            "COMPANY": 4,
            "INVOICE": 5,
            "SMART_INVOICE": 31,
            "QUOTE": 7,
            "REQUISITE": 8
        }
        return entityTypeCodeToId.get(placement)

    def __callBatch(self, msgList = [], updateFields = {}):     
        msg = '%0A'.join(msgList)      

        if self.placement == "DYNAMIC": 
          entityTypeId = self.entityTypeId
          entityType = "DYNAMIC_{entityTypeId}".format(entityTypeId = self.entityTypeId)
        else:
          entityTypeId = self.__getEntityTypeCodeToId(self.placement)
          entityType = self.placement

        batch={
            'get_crm': 'crm.item.get', 
            'notify': 'im.notify', 
            'livefeedmessage': 'crm.timeline.comment.add'
        }
        batchParams={
            'get_crm': {
                'id': '{elementId}'.format(elementId=self.elementId),
                'entityTypeId': '{entityTypeId}'.format(entityTypeId=entityTypeId),
                'select': ['assignedById','title']
            },
            'notify': {
                'to': '$result[get_crm][item][assignedById]', 
                'type': 'SYSTEM', 
                'message': '{msg}'.format(msg=msg)
            }, 
            'livefeedmessage': {
                'fields': {
                    'ENTITY_TYPE': '{placement}'.format(placement=entityType), 
                    'ENTITY_ID': '{elementId}'.format(elementId=self.elementId),
                    'COMMENT': '{msg}'.format(msg=msg)
                }
            }
        }
        el = self.__bx24.callBatch(batch=batch, batch_params=batchParams)
        return el

    def getActualData(self): 
        if self.__getAppSettings() and (self.timestamp + (3600*24)*1000000) > int(time.time()*1000000) :
            logging.info("actual data: jsonKAD ={jsonKAD}, search = {search}".format(jsonKAD=self.jsonKAD, search=self.search))
            return {
              "jsonKAD": json.loads(self.jsonKAD),
              "search": self.search,
              "track": self.track,
              "timestamp": self.timestamp
            }
        else:
            logging.info("need update data")
            try:
                if self.placement == "DYNAMIC":
                  entityTypeId = self.entityTypeId
                else:
                  entityTypeId = self.__getEntityTypeCodeToId(self.placement)

                el = self.__bx24.call('crm.item.get', {
                    'entityTypeId': entityTypeId,
                    'id': self.elementId
                })
                v = el.get("result").get("item")
                logging.info("crm.item.get: {v}".format(v=v))
                search = False
                for k in v:
                  if "KadSearch" in k and type(v[k]) == str and len(v[k]):                    
                    search = v[k]
            except:
                search = False

            logging.info("search: {search}".format(search=search))

            if type(search) == str and len(search):
              res = self.getSearch(search)
              logging.info("search result: {res}".format(res=res))

              if res.get("code") == 200:
                if self.track == True:
                  self.__compare(res.get("json"))

                self.__setAppSettings(jsonKAD = res.get("text"), search = search)
                self.__getAppSettings()
                return {
                  "jsonKAD": json.loads(self.jsonKAD),
                  "search": self.search,
                  "track": self.track,
                  "timestamp": self.timestamp
                }
              else:
                return {
                  "jsonKAD": json.loads(self.jsonKAD),
                  "search": self.search,
                  "track": self.track,
                  "timestamp": self.timestamp,
                  "error": "Данные не получены. Ошибка ответа Кад.Арбитр. Статус ответа: " + res.get("code"),
                }
            else:
                try:
                    self.__setAppSettings(jsonKAD = self.jsonKAD, search = self.search)
                except:
                    self.__setAppSettings()  
                    
                return {
                  "error": 'Не заполено поле "Поиск в Кад.Арбитр"',
                }
