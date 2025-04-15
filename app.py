from flask import Flask, render_template, jsonify

app = Flask(__name__)

# Данные товаров
items = [
    {'id': 1, 'name': 'Товар 1', 'description': 'Описание товара 1', 'price': 50},
    {'id': 2, 'name': 'Товар 2', 'description': 'Описание товара 2', 'price': 100},
    {'id': 3, 'name': 'Товар 3', 'description': 'Описание товара 3', 'price': 150}
]

@app.route('/')
def index():
    return render_template('index.html', items=items)

# Обработчик для подтверждения покупки
@app.route('/confirm_purchase/<int:item_id>', methods=['POST'])
def confirm_purchase(item_id):
    # Здесь можно обработать подтверждение покупки
    return jsonify({'status': 'success', 'message': f'Вы купили товар с id {item_id}!'})

if __name__ == '__main__':
    app.run(debug=True)
