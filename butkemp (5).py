import asyncio
import random
import time
import requests
import secret

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import ReplyKeyboardRemove


main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="ℹ️ Информация")],
        [KeyboardButton(text="📝 Регистрация"), KeyboardButton(text="🔑 Вспомнить логин")],
        [KeyboardButton(text="❓ Неотвеченные вопросы"), KeyboardButton(text="📜 Все вопросы")],
        [KeyboardButton(text="📊 Топ вопросов"), KeyboardButton(text="💬 Задать вопрос")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
    input_field_placeholder="Выберите действие..."
)



bin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="да"), KeyboardButton(text="нет")]
    ],
    resize_keyboard=True
)

teachers = {}
questions = {}
answered_questions={}
equation_solutions = {
    1001: ("Как решать квадратные уравнения?", "Квадратное уравнение имеет вид ax^2 + bx + c = 0. "
                                        "Решается через дискриминант: D = b^2 - 4ac. Если D > 0, "
                                        "то два корня: x1 = (-b + sqrt(D)) / 2a, x2 = (-b - sqrt(D)) / 2a. "
                                        "Если D = 0, то один корень x = -b / 2a. Если D < 0, решений нет."),
    1002: ("Методы решения линейных уравнений", "Линейные уравнения вида ax + b = 0 решаются переносом и делением: x = -b/a."),
    1003: ("Как найти корни кубического уравнения?", "Корни кубического уравнения можно найти с помощью метода Кардано или разложения на множители."),
    1004: ("Как найти площадь прямоугольника?", "Площадь = длина × ширина."),
    1005: ("Что такое периметр?", "Периметр - сумма всех сторон фигуры."),
    1006: ("Что такое процент?", "Процент - это дробь с основанием 100."),
    1007: ("Что такое функция?", "Функция - соответствие между элементами двух множеств"),
    1008: ("Как найти среднее арифметическое?", "Среднее = сумма всех значений / количество значений"),
    1009: ("Как вывести текст на экран?", "Используйте функцию print(""Ваш текст"")."),
    1010: ("Как создать переменную?", "Просто присвойте значение: x = 10.")
}
questions_statistic={}
class Registration(StatesGroup):
    waiting_for_teacher_name = State()

class Question(StatesGroup):
    waiting_for_teacher_id = State()
    waiting_for_question = State()
    waiting_for_student_decision = State()

async def start(message: Message) -> None:
    await message.answer(
        "Привет! Это чат-бот проекта Проводка!\n\n"
        "Выберите команду из списка.",
        reply_markup=main_keyboard,
        input_field_placeholder="Выберите команду..."
    )

async def register_teacher(message: Message, state: FSMContext) -> None:
    await state.set_state(Registration.waiting_for_teacher_name)
    await message.answer("Введите ваш логин, чтобы зарегистрироваться как преподаватель.",reply_markup=ReplyKeyboardRemove())

async def save_teacher(message: Message, state: FSMContext) -> None:
    teacher_id = message.from_user.id
    if message.text in teachers.values():
        await message.answer("Такой логин уже занят.",reply_markup=ReplyKeyboardRemove())
        return
    teachers[teacher_id] = message.text
    await state.clear()
    await message.answer(f"Вы зарегистрированы как преподаватель! Ваш логин: `{teachers[teacher_id]}`",reply_markup=main_keyboard)

async def ask_question(message: Message, state: FSMContext) -> None:
    await state.set_state(Question.waiting_for_teacher_id)
    await message.answer("Введите логин преподавателя, которому хотите задать вопрос:",reply_markup=ReplyKeyboardRemove())

async def get_teacher_id(message: Message, state: FSMContext) -> None:
    try:
        teacher_login = message.text
        if teacher_login not in teachers.values():
            await message.answer("Преподаватель с таким логином не найден. Попробуйте снова.",reply_markup=main_keyboard)
            await state.clear()
        else:
            for key in teachers.keys():
                if teachers[key]==teacher_login:
                    await state.update_data(teacher_login=key)
            await state.set_state(Question.waiting_for_question)
            await message.answer("Введите ваш вопрос:",reply_markup=ReplyKeyboardRemove())
    except Exception:
        await message.answer("Некорректный логин. Попробуйте еще раз.",reply_markup=ReplyKeyboardRemove())

async def find_similar_question(question: str) -> tuple:
    folder_id = secret.folder_id
    api_key = secret.api_key
    gpt_model = "yandexgpt-lite"

    existing_questions = "\n".join(f"{q_id}: {q_text[0]}" for q_id, q_text in equation_solutions.items())

    prompt = (
        f"У тебя есть база вопросов и их номеров:\n\n"
        f"{existing_questions}\n\n"
        f"Вопрос студента: {question}\n\n"
        f"Определи, есть ли похожий вопрос в базе. Верни ТОЛЬКО номер похожего вопроса. "
        f"Если совпадения нет, напиши 'None'."
    )

    body = {
        "modelUri": f"gpt://{folder_id}/{gpt_model}",
        "completionOptions": {"stream": False, "temperature": 0.3, "maxTokens": 1000},
        "messages": [{"role": "system", "text": "Ты помощник преподавателя для ответа на вопросы."},
                     {"role": "user", "text": prompt}],
    }

    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completionAsync"
    headers = {"Content-Type": "application/json", "Authorization": f"Api-Key {api_key}"}

    response = requests.post(url, headers=headers, json=body)
    operation_id = response.json().get("id")

    url = f"https://llm.api.cloud.yandex.net:443/operations/{operation_id}"
    while True:
        response = requests.get(url, headers=headers)
        if response.json().get("done"):
            break
        time.sleep(1)

    result = response.json()["response"]["alternatives"][0]["message"]["text"].strip()

    if result.isdigit():
        q_id = int(result)
        # questions_statistic[q_id]=questions_statistic.get(q_id,0)+1
        if q_id in equation_solutions:
            return q_id, equation_solutions[q_id][1]

    return None, None

async def send_question(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    teacher_id = data["teacher_login"]
    student_id = message.from_user.id
    question_text = message.text.strip()

    existing_q_id, existing_answer = await find_similar_question(question_text)
    if existing_answer:
        if teacher_id not in questions_statistic:
            questions_statistic[teacher_id] = {}  # Создаём пустой словарь для преподавателя

        questions_statistic[teacher_id][existing_q_id] = questions_statistic[teacher_id].get(existing_q_id, 0) + 1

        await state.update_data(question_text=question_text)
        await state.set_state(Question.waiting_for_student_decision)
        await message.answer(
            f"🔍 Найден похожий вопрос! Его номер: `{existing_q_id}`\n\n"
            f"📌 Вопрос: {equation_solutions[existing_q_id][0]}\n"
            f"💬 Ответ: {existing_answer}\n\n"
            "Устраивает ли вас этот ответ? (да/нет)",reply_markup=bin_keyboard
        )
        return

    await forward_question_to_teacher(message, state, bot, question_text, teacher_id)

async def handle_student_decision(message: Message, state: FSMContext, bot: Bot) -> None:
    decision = message.text.strip().lower()
    data = await state.get_data()
    question_text = data["question_text"]
    teacher_id = data["teacher_login"]

    if decision == "да":
        await state.clear()
        await message.answer("Отлично! Если появятся новые вопросы, обращайтесь.",reply_markup=main_keyboard)
    elif decision == "нет":
        await forward_question_to_teacher(message, state, bot, question_text, teacher_id)
    else:
        await message.answer("Пожалуйста, ответьте 'да' или 'нет'.",reply_markup=bin_keyboard)

async def forward_question_to_teacher(message: Message, state: FSMContext, bot: Bot, question_text: str, teacher_id: int) -> None:
    student_id = message.from_user.id
    question_id = random.randint(10000, 99999)

    if teacher_id not in questions:
        questions[teacher_id] = {}
    questions[teacher_id][question_id] = (student_id, question_text)
    answered_questions[question_id]=0
    await bot.send_message(
        teacher_id,
        f"📩 Новый вопрос (ID: {question_id}) от {message.from_user.full_name}:\n"
        f"💬 {question_text}\n\n"
        "Ответьте, начав сообщение с ID вопроса (например, `12345 Ваш ответ`).",reply_markup=main_keyboard
    )

    await state.clear()
    await message.answer(f"Ваш вопрос отправлен преподавателю! Его ID: `{question_id}`",reply_markup=main_keyboard)

async def handle_teacher_response(message: Message, bot: Bot) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[0].isdigit():
        await message.answer("Попробуйте выбрать команду из списка.",
                             reply_markup=main_keyboard
                             )
        return

    question_id = int(parts[0])
    reply_text = parts[1]

    teacher_id = message.from_user.id
    if teacher_id not in questions or question_id not in questions[teacher_id]:
        await message.answer("Ошибка: вопрос с таким ID не найден.",reply_markup=main_keyboard)
        return

    student_id, question_text = questions[teacher_id][question_id]
    answered_questions[question_id]=1
    await bot.send_message(
        student_id,
        f"📢 Ответ от преподавателя:\n"
        f"📌 Ваш вопрос (ID {question_id}): {question_text}\n"
        f"💬 Ответ: {reply_text}",reply_markup=main_keyboard
    )
    await message.answer("Ответ отправлен студенту!",reply_markup=main_keyboard)


async def list_all_questions(message: Message) -> None:
    teacher_id = message.from_user.id
    if teacher_id not in questions or not questions[teacher_id]:
        await message.answer("У вас пока нет вопросов.",reply_markup=main_keyboard)
        return

    text = "📋 Все вопросы, которые вам задавали:\n\n"
    for q_id, (student_id, question_text) in questions[teacher_id].items():
        text += f"🔹 *ID:* `{q_id}`\n💬 *Вопрос:* {question_text}\n\n"

    await message.answer(text,reply_markup=main_keyboard)


async def info(message: Message) -> None:
    await message.answer("🚀 Идея проекта\n"
"Наш проект — это платформа для преподавателей с богатым опытом, позволяющая эффективно масштабировать образовательные курсы по всему миру благодаря уникальному ИИ-помощнику и технологии автоматического перевода в режиме реального времени.\n\n"
"🎯 Какие проблемы мы решаем:\n"
"Перегруженность преподавателей: Постоянное повторение лекций отнимает много времени и энергии.\n"
"Ограниченность аудитории: Языковой барьер не позволяет привлечь международных студентов.\n"
"Потеря потенциального дохода: Преподаватели не используют полностью возможности монетизации своих курсов.\n",
                         reply_markup=main_keyboard
                         )

async def list_unanswered_questions(message: Message) -> None:
    teacher_id = message.from_user.id
    if teacher_id not in questions or not questions[teacher_id]:
        await message.answer("У вас нет неотвеченных вопросов.",reply_markup=main_keyboard)
        return

    unanswered = {q_id: q_text for q_id, q_text in questions[teacher_id].items() if answered_questions[q_id]==0}

    text = "📋 Неотвеченные вопросы:\n\n"
    for q_id, (student_id, question_text) in unanswered.items():
        text += f"🔹 *ID:* `{q_id}`\n💬 *Вопрос:* {question_text}\n\n"

    await message.answer(text,reply_markup=main_keyboard)

async def remember_login(message: Message) -> None:
    teacher_id = message.from_user.id
    if teacher_id not in teachers:
        await message.answer("Вы не зарегистрировались как преподаватель.")
    else:
        await message.answer(f"Ваш логин: {teachers[teacher_id]}.",reply_markup=main_keyboard)

def comporator(a):
    return a[1]
async def count_question(message: Message) -> None:
    answer = ''
    teacher_id=message.from_user.id
    if teacher_id in questions_statistic.keys():
        sort_list=[[key,value] for key,value in questions_statistic[teacher_id].items()]
        sort_list.sort(key=comporator)
        sort_list=sort_list[::-1]
        for i in range(min(len(sort_list),5)):
            answer += f'{sort_list[i][1]} раз(а) - {equation_solutions[sort_list[i][0]][0]} \n\n'
    if len(answer) != 0:
        await message.answer(answer,reply_markup=main_keyboard)
    else:
        await message.answer("Вопросов ещё не задавали.",reply_markup=main_keyboard)
async def main() -> None:
    bot = Bot(token=secret.bot_token)
    dp = Dispatcher()

    dp.message.register(start, Command("start"))
    dp.message.register(register_teacher, Command("register"))
    dp.message.register(save_teacher, Registration.waiting_for_teacher_name)
    dp.message.register(ask_question, Command("ask"))
    dp.message.register(get_teacher_id, Question.waiting_for_teacher_id)
    dp.message.register(send_question, Question.waiting_for_question)
    dp.message.register(handle_student_decision, Question.waiting_for_student_decision)
    dp.message.register(list_all_questions, Command("all_questions"))
    dp.message.register(list_unanswered_questions, Command("unans_questions"))
    dp.message.register(remember_login, Command("remember_login"))
    dp.message.register(count_question, Command("count_question"))
    dp.message.register(info, Command("info"))
    dp.message.register(info, F.text == "ℹ️ Информация")
    dp.message.register(register_teacher, F.text == "📝 Регистрация")
    dp.message.register(remember_login, F.text == "🔑 Вспомнить логин")
    dp.message.register(list_unanswered_questions, F.text == "❓ Неотвеченные вопросы")
    dp.message.register(list_all_questions, F.text == "📜 Все вопросы")
    dp.message.register(count_question, F.text == "📊 Топ вопросов")
    dp.message.register(ask_question, F.text == "💬 Задать вопрос")

    dp.message.register(handle_teacher_response, F.text)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
