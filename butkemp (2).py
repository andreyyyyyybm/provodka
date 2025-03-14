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

teachers = {}
questions = {}
answered_questions={}
equation_solutions = {
    1001: ("Как решать квадратные уравнения?", "Чтобы решить квадратное уравнение ax² + bx + c = 0, используйте дискриминант D = b² - 4ac..."),
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
        "Привет! Ты студент или преподаватель?\n\n"
        "Если ты преподаватель, напиши /register, чтобы получить ID.\n\n"
        "Посмотреть свой id: /remember_id.\n\n"
         "Посмотреть неотвеченные вопросы: /unanswered_questions.\n\n"
         "Посмотреть неотвеченные вопросы: /all_questions.\n\n"
        "Посмотреть топ 5 вопросов: /count_question.\n\n"
         "Если ты студент, напиши /ask, чтобы задать вопрос."
    )

async def register_teacher(message: Message, state: FSMContext) -> None:
    await state.set_state(Registration.waiting_for_teacher_name)
    await message.answer("Введите ваше имя, чтобы зарегистрироваться как преподаватель.")

async def save_teacher(message: Message, state: FSMContext) -> None:
    teacher_id = message.from_user.id
    teachers[teacher_id] = message.text
    await state.clear()
    await message.answer(f"Вы зарегистрированы как преподаватель! Ваш ID: `{teacher_id}`")

async def ask_question(message: Message, state: FSMContext) -> None:
    await state.set_state(Question.waiting_for_teacher_id)
    await message.answer("Введите ID преподавателя, которому хотите задать вопрос:")

async def get_teacher_id(message: Message, state: FSMContext) -> None:
    try:
        teacher_id = int(message.text)
        if teacher_id not in teachers:
            await message.answer("Преподаватель с таким ID не найден. Попробуйте снова.")
            return
        await state.update_data(teacher_id=teacher_id)
        await state.set_state(Question.waiting_for_question)
        await message.answer("Введите ваш вопрос:")
    except ValueError:
        await message.answer("Некорректный ID. Введите число.")

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
        questions_statistic[q_id]=questions_statistic.get(q_id,0)+1
        if q_id in equation_solutions:
            return q_id, equation_solutions[q_id][1]

    return None, None

async def send_question(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    teacher_id = data["teacher_id"]
    student_id = message.from_user.id
    question_text = message.text.strip()

    existing_q_id, existing_answer = await find_similar_question(question_text)
    if existing_answer:
        await state.update_data(question_text=question_text)
        await state.set_state(Question.waiting_for_student_decision)
        await message.answer(
            f"🔍 Найден похожий вопрос! Его номер: `{existing_q_id}`\n\n"
            f"📌 Вопрос: {equation_solutions[existing_q_id][0]}\n"
            f"💬 Ответ: {existing_answer}\n\n"
            "Устраивает ли вас этот ответ? (да/нет)"
        )
        return

    await forward_question_to_teacher(message, state, bot, question_text, teacher_id)

async def handle_student_decision(message: Message, state: FSMContext, bot: Bot) -> None:
    decision = message.text.strip().lower()
    data = await state.get_data()
    question_text = data["question_text"]
    teacher_id = data["teacher_id"]

    if decision == "да":
        await state.clear()
        await message.answer("Отлично! Если появятся новые вопросы, обращайтесь.")
    elif decision == "нет":
        await forward_question_to_teacher(message, state, bot, question_text, teacher_id)
    else:
        await message.answer("Пожалуйста, ответьте 'да' или 'нет'.")

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
        "Ответьте, начав сообщение с ID вопроса (например, `12345 Ваш ответ`)."
    )

    await state.clear()
    await message.answer(f"Ваш вопрос отправлен преподавателю! Его ID: `{question_id}`")

async def handle_teacher_response(message: Message, bot: Bot) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[0].isdigit():
        await message.answer("Вот список команд:\n"
                             "Если ты преподаватель, напиши /register, чтобы получить ID.\n\n"
                             "Посмотреть свой id: /remember_id.\n\n"
                             "Посмотреть неотвеченные вопросы: /unanswered_questions.\n\n"
                             "Посмотреть неотвеченные вопросы: /all_questions.\n\n"
                             "Посмотреть топ 5 вопросов: /count_question.\n\n"
                             "Если ты студент, напиши /ask, чтобы задать вопрос."
                             )
        return

    question_id = int(parts[0])
    reply_text = parts[1]

    teacher_id = message.from_user.id
    if teacher_id not in questions or question_id not in questions[teacher_id]:
        await message.answer("Ошибка: вопрос с таким ID не найден.")
        return

    student_id, question_text = questions[teacher_id][question_id]
    answered_questions[question_id]=1
    await bot.send_message(
        student_id,
        f"📢 Ответ от преподавателя:\n"
        f"📌 Ваш вопрос (ID {question_id}): {question_text}\n"
        f"💬 Ответ: {reply_text}"
    )
    await message.answer("Ответ отправлен студенту!")


async def list_all_questions(message: Message) -> None:
    teacher_id = message.from_user.id
    if teacher_id not in questions or not questions[teacher_id]:
        await message.answer("У вас пока нет вопросов.")
        return

    text = "📋 Все вопросы, которые вам задавали:\n\n"
    for q_id, (student_id, question_text) in questions[teacher_id].items():
        text += f"🔹 *ID:* `{q_id}`\n💬 *Вопрос:* {question_text}\n\n"

    await message.answer(text)


async def list_unanswered_questions(message: Message) -> None:
    teacher_id = message.from_user.id
    if teacher_id not in questions or not questions[teacher_id]:
        await message.answer("У вас нет неотвеченных вопросов.")
        return

    unanswered = {q_id: q_text for q_id, q_text in questions[teacher_id].items() if answered_questions[q_id]==0}

    text = "📋 Неотвеченные вопросы:\n\n"
    for q_id, (student_id, question_text) in unanswered.items():
        text += f"🔹 *ID:* `{q_id}`\n💬 *Вопрос:* {question_text}\n\n"

    await message.answer(text)

async def remember_id(message: Message) -> None:
    teacher_id = message.from_user.id
    await message.answer(f"Ваш id: {teacher_id}.")

def comporator(a):
    return a[1]
async def count_question(message: Message) -> None:
    answer = ''
    sort_list=[[key,value] for key,value in questions_statistic.items()]
    sort_list.sort(key=comporator)
    for i in range(min(len(sort_list),5)):
        answer += f'{sort_list[i][1]} раз(а) - {equation_solutions[sort_list[i][0]][0]} \n\n'
    if len(answer) != 0:
        await message.answer(answer)
    else:
        await message.answer("Вопросов ещё не задавали")
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
    dp.message.register(list_unanswered_questions, Command("unanswered_questions"))
    dp.message.register(remember_id, Command("remember_id"))
    dp.message.register(count_question, Command("count_question"))
    dp.message.register(handle_teacher_response, F.text)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
