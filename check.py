from main import app
routes = [r.path for r in app.routes]
print('Total routes:', len(routes))
for r in routes:
    print(r)