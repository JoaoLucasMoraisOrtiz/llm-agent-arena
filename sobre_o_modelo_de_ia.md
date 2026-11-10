Exemplos de Uso                                                     
                                                                             
  #### Via cURL                                                              
                                                                             
    curl -X POST "https://llm.bambuagromarketing.tech/litellm/v1/messages" \ 
      -H "Authorization: Bearer sk-ccLw1Qk0SxjNYlaW950rOA" \                 
      -H "x-api-key: sk-ccLw1Qk0SxjNYlaW950rOA" \                            
      -H "anthropic-version: 2023-06-01" \                                   
      -H "Content-Type: application/json" \                                  
      -d '{                                                                  
        "model": "MiniMax-M3-Imersa",                                        
        "max_tokens": 256,                                                   
        "messages": [                                                        
          {"role": "user", "content": "Olá, tudo bem?"}                      
        ]                                                                    
      }'                                                                     
                                                                             
  #### Via Python (com SDK da Anthropic)                                     
                                                                             
    from anthropic import Anthropic                                          
                                                                             
    client = Anthropic(                                                      
        base_url="https://llm.bambuagromarketing.tech/litellm",              
        api_key="sk-ccLw1Qk0SxjNYlaW950rOA"                                  
    )                                                                        
                                                                             
    response = client.messages.create(                                       
        model="MiniMax-M3-Imersa",                                           
        max_tokens=300,                                                      
        messages=[                                                           
            {"role": "user", "content": "Explique o que é a plataforma       
  Imersa."}                                                                  
        ]                                                                    
    )                                                                        
                                                                             
    print(response.content[0].text)                                          
                                                                             
  #### Via Python (sem bibliotecas externas / nativo)                        
                                                                             
    import urllib.request                                                    
    import json                                                              
                                                                             
    url = "https://llm.bambuagromarketing.tech/litellm/v1/messages"          
    headers = {
        "Authorization": "Bearer sk-ccLw1Qk0SxjNYlaW950rOA",
        "x-api-key": "sk-ccLw1Qk0SxjNYlaW950rOA",
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "MiniMax-M3-Imersa",
        "max_tokens": 150,
        "messages": [{"role": "user", "content": "Olá!"}]
    }
  
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-  
  8"), headers=headers)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(data["content"][0]["text"])