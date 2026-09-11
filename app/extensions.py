from flask_caching import Cache
# App-level cache instance 
# This is in a separate file to prevent circular imports
cache = Cache()