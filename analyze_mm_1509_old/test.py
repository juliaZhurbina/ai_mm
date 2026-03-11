import pandas as pd

orders_df = pd.read_csv('orders.csv')
products_df = pd.read_csv('products.csv')

# 1. Преобразовать поле order_date в datetime.
orders_df['order_date'] = pd.to_datetime(orders_df['order_date'])

# 2. Объединить оба датасета по product_id
merged_df = pd.merge(orders_df, products_df, on='product_id', how='left')

# 3. Вычислить сумму заказа (quantity * price) и добавить этот столбец
merged_df['order_sum'] = merged_df['quantity'] * merged_df['price']

# 4. Добавить новый столбец с номером месяца заказа (order_month)
merged_df['order_month'] = merged_df['order_date'].dt.month

# 5. Сгруппировать данные по customer_id
customer_stats = merged_df.groupby('customer_id').agg({
    'quantity': 'sum',  # общее количество заказанных товаров
    'order_sum': 'sum',  # общая сумма заказов
    'category': 'nunique'  # количество уникальных категорий товаров
}).reset_index()  #.reset_index() - сбрасываем индекс, чтобы customer_id стал обычным столбцом

# 6. Вывести топ-5 покупателей по сумме заказов
top5_customers = customer_stats.nlargest(5, 'order_sum')

# 7. Удалить столбец category (из customer_stats)
customer_stats_final = customer_stats.drop('category', axis=1)

# 8. Изменитт названия столбцов
customer_stats_final.columns = ['ID_Покупателя', 'Количество', 'Сумма']

# 9. Создать новый столбец Группа
customer_stats_final['Группа'] = customer_stats_final['Сумма'].apply(
    lambda x: 'больше 3000' if x >= 3000 else 'меньше 3000'
)

# 10. Сохраняем топ-5 покупателей в файл xlsx
with pd.ExcelWriter('топ5_покупатели.xlsx') as writer:
    top5_customers_final = customer_stats_final.nlargest(5, 'Сумма')
    top5_customers_final.to_excel(writer, sheet_name='Топ5', index=False)

