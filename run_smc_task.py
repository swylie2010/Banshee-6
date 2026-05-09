
import os
import sys

# Add the directory to sys.path so we can import everything correctly
script_dir = r"C:\Users\swyli\AntiEverything\Banshee_Pro_3"
sys.path.insert(0, script_dir)

# Import the mcp_server modules to access the tool functions
import mcp_server

def main():
    symbol = 'BTC/USD'
    ltf = '4h'
    htf = '1d'
    use_ai = True
    
    print(f"Running get_smc_structure for {symbol} (LTF: {ltf}, HTF: {htf}, AI: {use_ai})...")
    
    try:
        # Call the get_smc_structure function directly from mcp_server
        result = mcp_server.get_smc_structure(symbol=symbol, ltf=ltf, htf=htf, use_ai=use_ai)
        print("\n--- RESULTS ---\n")
        print(result)
    except Exception as e:
        print(f"Error running SMC tool: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
