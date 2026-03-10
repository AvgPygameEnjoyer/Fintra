import sys
from upstash_redis import Redis

if len(sys.argv) < 3:
    print("Usage: python test_upstash_connection.py <UPSTASH_HOST> <UPSTASH_REST_TOKEN>")
    print("Example: python test_upstash_connection.py diverse-jackal-66427.upstash.io YOUR_API_TOKEN_HERE")
    sys.exit(1)

host = sys.argv[1]
token = sys.argv[2]

rest_url = host if host.startswith('http') else f"https://{host}"

print(f"\nTesting Upstash REST connection...")
print(f"URL: {rest_url}")
print(f"Token: {token[:6]}...{token[-4:]}\n")

try:
    redis = Redis(url=rest_url, token=token)
    
    # Test 1: PING
    ping_result = redis.ping()
    print(f"✅ PING successful: {ping_result}")
    
    # Test 2: READ (GET)
    get_result = redis.get('fintra_test_key')
    print(f"✅ READ (GET) successful: (returned {get_result})")

    # Test 3: WRITE (SET) - This is the crucial test that threw NOPERM before
    set_result = redis.set('fintra_test_key', 'it_works', ex=10)
    print(f"✅ WRITE (SET) successful: {set_result}")
    
    # Cleanup
    redis.delete('fintra_test_key')
    
    print("\n🎉 SUCCESS: Full Read/Write verification complete!")
    print("This API Key is valid and has the correct Write permissions. You can use it in REDIS_API_KEY.")
    
except Exception as e:
    print(f"\n❌ OPERATION FAILED:")
    print(f"{type(e).__name__}: {e}")
    
    if "NOPERM" in str(e):
        print("\n⚠️ VERDICT: This token is READ-ONLY. It successfully connected, but Upstash blocked the write.")
        print("Please generate an API Token with Write/Admin permissions in the Upstash console.")
