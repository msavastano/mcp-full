
import { GEMINI_API_KEY } from '../config';
import { webSocketService } from './websocket';

const API_URL = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${GEMINI_API_KEY}`;

export const callGemini = async (prompt: string, tools: any[], resources: any[] = []) => {
  // Add a resource reading tool for animals if resources are available
  const resourceTools = resources.length > 0 ? [{
    name: "read_animal_info",
    description: "Read information about animals (dolphin, elephant, lion) from resources",
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
  }] : [];

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
            // Handle resource reading for animals
            const animal = functionCall.functionCall.args?.animal || functionCall.functionCall.arguments?.animal;
            const resourceUri = `animal://${animal}`;
            console.log('Reading resource:', resourceUri);
            
            toolResponse = await webSocketService.readResource(resourceUri);
            console.log('Resource response:', JSON.stringify(toolResponse, null, 2));
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
      
      // Send tool results back to Gemini for final response
      const finalRequestBody = {
        contents: [
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
        ],
        tools: [{ function_declarations: allTools }]
      };
      
      const finalResponse = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(finalRequestBody)
      });
      
      if (!finalResponse.ok) {
        throw new Error(`HTTP error! status: ${finalResponse.status}`);
      }
      
      const finalData = await finalResponse.json();
      console.log('Gemini Final Response:', JSON.stringify(finalData, null, 2));
      return finalData;
    }
    
    return data;
  } catch (error) {
    console.error('Error calling Gemini API:', error);
    throw error;
  }
};
