"""Debug script to inspect Gateway tools."""
import asyncio
import json
from gateway_client import create_mcp_client, load_gateway_tools

async def main():
    print("Loading Gateway tools...")
    mcp_client = create_mcp_client()
    tools = await load_gateway_tools(mcp_client)
    
    print(f"\nFound {len(tools)} tools:")
    print("=" * 60)
    
    for tool in tools:
        print(f"\nTool attributes:")
        print(f"  Type: {type(tool)}")
        
        # Try to extract all relevant attributes
        name = getattr(tool, 'name', None) or getattr(tool, 'tool_name', None)
        description = getattr(tool, 'description', None)
        input_schema = getattr(tool, 'input_schema', None)
        tool_spec = getattr(tool, 'tool_spec', None)
        
        print(f"\n  Name: {name}")
        print(f"  Description: {description}")
        print(f"  Input Schema: {json.dumps(input_schema, indent=4) if input_schema else 'None'}")
        
        if tool_spec:
            print(f"\n  TOOL_SPEC Found:")
            print(f"    {json.dumps(tool_spec, indent=4)}")
        
        print("-" * 60)

if __name__ == "__main__":
    asyncio.run(main())
