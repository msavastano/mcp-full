import { webSocketService } from './websocket';

const API_URL = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${import.meta.env.VITE_GEMINI_API_KEY}`;

export const callGemini = async (prompt: string, tools: any[], resources: any[] = []) => {
  // Add resource reading tools if resources are available
  const resourceTools = resources.length > 0 ? [
    {
      name: "read_animal_info",
      description: "Read basic information about animals from static resources",
      parameters: {
        type: "object",
        properties: {
          animal: {
            type: "string",
            description: "The animal to get information about (dolphin, elephant, lion, or cloudwhale)",
            enum: ["dolphin", "elephant", "lion", "cloudwhale"]
          }
        },
        required: ["animal"]
      }
    },
    {
      name: "get_weather_report",
      description: "Generate dynamic weather report for any location and time period using resource templates",
      parameters: {
        type: "object",
        properties: {
          location: {
            type: "string",
            description: "Location for weather report (providence-ri, boston-ma, new-york-ny, los-angeles-ca, chicago-il)"
          },
          days: {
            type: "string",
            description: "Number of days for forecast (1-14)"
          }
        },
        required: ["location", "days"]
      }
    },
    {
      name: "get_animal_facts",
      description: "Get specific facts about animals by category using dynamic resource templates",
      parameters: {
        type: "object",
        properties: {
          species: {
            type: "string",
            description: "Animal species (dolphin, elephant, lion, cloudwhale)"
          },
          category: {
            type: "string",
            description: "Fact category (habitat, diet, behavior, conservation, physical, reproduction)"
          }
        },
        required: ["species", "category"]
      }
    },
    {
      name: "get_climate_data",
      description: "Get historical climate data for specific location and time using resource templates",
      parameters: {
        type: "object",
        properties: {
          location: {
            type: "string",
            description: "Location for climate data"
          },
          year: {
            type: "string",
            description: "Year for climate data (1900-2024)"
          },
          month: {
            type: "string",
            description: "Month for climate data (1-12)"
          }
        },
        required: ["location", "year", "month"]
      }
    }
  ] : [];

  const allTools = [...tools, ...resourceTools];

  const requestBody = {
    contents: [
      {
        role: 'user',
        parts: [
          {
            text: prompt,
          },
        ],
      },
    ],
    tools: [
      {
        function_declarations: allTools,
      },
    ],
  };

  try {
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    console.log('Gemini API Response:', data);
    
    // Check if Gemini wants to call tools
    const candidate = data.candidates?.[0];
    const functionCalls = candidate?.content?.parts?.filter((part: any) => part.functionCall);
    
    if (functionCalls && functionCalls.length > 0) {
      console.log('Gemini requested tool calls:', JSON.stringify(functionCalls, null, 2));
      
      // Execute each tool call via MCP WebSocket
      const toolResults = [];
      for (const functionCall of functionCalls) {
        try {
          let toolResponse;
          
          if (functionCall.functionCall.name === "read_animal_info") {
            // Handle static animal resource reading
            const animal = functionCall.functionCall.args?.animal || functionCall.functionCall.arguments?.animal;
            const resourceUri = `animal://${animal}`;
            console.log('Reading static resource:', resourceUri);
            
            toolResponse = await webSocketService.readResource(resourceUri);
            console.log('Resource response:', JSON.stringify(toolResponse, null, 2));
          } else if (functionCall.functionCall.name === "get_weather_report") {
            // Handle dynamic weather report resource template
            const args = functionCall.functionCall.args || functionCall.functionCall.arguments;
            const location = args?.location;
            const days = args?.days;
            const resourceUri = `weather://report/${location}/${days}`;
            console.log('Reading dynamic weather resource:', resourceUri);
            
            toolResponse = await webSocketService.readResource(resourceUri);
            console.log('Weather resource response:', JSON.stringify(toolResponse, null, 2));
          } else if (functionCall.functionCall.name === "get_animal_facts") {
            // Handle dynamic animal facts resource template
            const args = functionCall.functionCall.args || functionCall.functionCall.arguments;
            const species = args?.species;
            const category = args?.category;
            const resourceUri = `animal://facts/${species}/${category}`;
            console.log('Reading dynamic animal facts resource:', resourceUri);
            
            toolResponse = await webSocketService.readResource(resourceUri);
            console.log('Animal facts resource response:', JSON.stringify(toolResponse, null, 2));
          } else if (functionCall.functionCall.name === "get_climate_data") {
            // Handle dynamic climate data resource template
            const args = functionCall.functionCall.args || functionCall.functionCall.arguments;
            const location = args?.location;
            const year = args?.year;
            const month = args?.month;
            const resourceUri = `climate://${location}/${year}/${month}`;
            console.log('Reading dynamic climate resource:', resourceUri);
            
            toolResponse = await webSocketService.readResource(resourceUri);
            console.log('Climate resource response:', JSON.stringify(toolResponse, null, 2));
          } else {
            // Handle regular tool calls
            const mcpRequest = {
              "jsonrpc": "2.0",
              "id": Date.now(),
              "method": "tools/call",
              "params": {
                "name": functionCall.functionCall.name,
                "arguments": functionCall.functionCall.args || functionCall.functionCall.arguments
              }
            };
            console.log('Sending MCP request:', JSON.stringify(mcpRequest, null, 2));
            
            toolResponse = await webSocketService.sendRequest(mcpRequest);
            console.log('MCP response:', JSON.stringify(toolResponse, null, 2));
          }
          
          toolResults.push({
            functionResponse: {
              name: functionCall.functionCall.name,
              response: toolResponse.result
            }
          });
        } catch (error) {
          console.error(`Error calling tool ${functionCall.functionCall.name}:`, error);
          toolResults.push({
            functionResponse: {
              name: functionCall.functionCall.name,
              response: { error: String(error) }
            }
          });
        }
      }
      
      // Continue conversation until we get a final text response
      let conversationHistory = [
        {
          role: 'user',
          parts: [{ text: prompt }]
        },
        {
          role: 'model',
          parts: functionCalls.map((fc: any) => ({ functionCall: fc.functionCall }))
        },
        {
          role: 'user',
          parts: toolResults
        }
      ];

      // Keep calling Gemini until we get a text response (not more function calls)
      let maxIterations = 5; // Prevent infinite loops
      let iteration = 0;
      
      while (iteration < maxIterations) {
        const continueRequestBody = {
          contents: conversationHistory,
          tools: [{ function_declarations: allTools }]
        };
        
        const continueResponse = await fetch(API_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(continueRequestBody)
        });
        
        if (!continueResponse.ok) {
          throw new Error(`HTTP error! status: ${continueResponse.status}`);
        }
        
        const continueData = await continueResponse.json();
        console.log(`Gemini Continue Response ${iteration + 1}:`, JSON.stringify(continueData, null, 2));
        
        const newCandidate = continueData.candidates?.[0];
        const newFunctionCalls = newCandidate?.content?.parts?.filter((part: any) => part.functionCall);
        
        if (newFunctionCalls && newFunctionCalls.length > 0) {
          // Gemini wants to call more tools
          console.log('Gemini requested more tool calls:', JSON.stringify(newFunctionCalls, null, 2));
          
          // Execute the new function calls
          const newToolResults = [];
          for (const functionCall of newFunctionCalls) {
            try {
              let toolResponse;
              
              if (functionCall.functionCall.name === "read_animal_info") {
                const animal = functionCall.functionCall.args?.animal || functionCall.functionCall.arguments?.animal;
                const resourceUri = `animal://${animal}`;
                toolResponse = await webSocketService.readResource(resourceUri);
              } else if (functionCall.functionCall.name === "get_weather_report") {
                const args = functionCall.functionCall.args || functionCall.functionCall.arguments;
                const location = args?.location;
                const days = args?.days;
                const resourceUri = `weather://report/${location}/${days}`;
                toolResponse = await webSocketService.readResource(resourceUri);
              } else if (functionCall.functionCall.name === "get_animal_facts") {
                const args = functionCall.functionCall.args || functionCall.functionCall.arguments;
                const species = args?.species;
                const category = args?.category;
                const resourceUri = `animal://facts/${species}/${category}`;
                toolResponse = await webSocketService.readResource(resourceUri);
              } else if (functionCall.functionCall.name === "get_climate_data") {
                const args = functionCall.functionCall.args || functionCall.functionCall.arguments;
                const location = args?.location;
                const year = args?.year;
                const month = args?.month;
                const resourceUri = `climate://${location}/${year}/${month}`;
                toolResponse = await webSocketService.readResource(resourceUri);
              } else {
                // Handle regular tool calls (including new get_coordinates)
                const mcpRequest = {
                  "jsonrpc": "2.0",
                  "id": Date.now(),
                  "method": "tools/call",
                  "params": {
                    "name": functionCall.functionCall.name,
                    "arguments": functionCall.functionCall.args || functionCall.functionCall.arguments
                  }
                };
                console.log('Sending MCP request:', JSON.stringify(mcpRequest, null, 2));
                
                toolResponse = await webSocketService.sendRequest(mcpRequest);
                console.log('MCP response:', JSON.stringify(toolResponse, null, 2));
              }
              
              newToolResults.push({
                functionResponse: {
                  name: functionCall.functionCall.name,
                  response: toolResponse.result
                }
              });
            } catch (error) {
              console.error(`Error calling tool ${functionCall.functionCall.name}:`, error);
              newToolResults.push({
                functionResponse: {
                  name: functionCall.functionCall.name,
                  response: { error: String(error) }
                }
              });
            }
          }
          
          // Add to conversation history
          conversationHistory.push({
            role: 'model',
            parts: newFunctionCalls.map((fc: any) => ({ functionCall: fc.functionCall }))
          });
          conversationHistory.push({
            role: 'user',
            parts: newToolResults
          });
          
          iteration++;
        } else {
          // Gemini returned a text response, we're done!
          console.log('Gemini provided final text response');
          return continueData;
        }
      }
      
      // If we hit max iterations, return the last response
      console.warn('Hit max iterations in multi-step tool calling');
      const finalRequestBody = {
        contents: conversationHistory,
        tools: [{ function_declarations: allTools }]
      };
      
      const finalResponse = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(finalRequestBody)
      });
      
      const finalData = await finalResponse.json();
      return finalData;
    }
    
    return data;
  } catch (error) {
    console.error('Error calling Gemini API:', error);
    throw error;
  }
};
