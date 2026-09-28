const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, AlignmentType, BorderStyle, ImageRun, PageBreak,
  Header, Footer, PageNumber, VerticalAlign
} = require("docx");

const PAGE_W = 11906; // A4 dxa
const PAGE_H = 16838;

function mono(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 0 },
    children: [new TextRun({ text, font: "Consolas", size: 17, ...opts })],
  });
}

function codeBlock(lines) {
  return lines.split("\n").map((l) => mono(l.length ? l : " "));
}

function h1(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_1, spacing: { before: 300, after: 150 } });
}
function h2(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 100 } });
}
function p(text, opts = {}) {
  return new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text, size: 22, ...opts })] });
}
function bullet(text) {
  return new Paragraph({ text, bullet: { level: 0 }, spacing: { after: 60 } });
}

function cell(text, opts = {}) {
  return new TableCell({
    width: opts.width ? { size: opts.width, type: WidthType.DXA } : undefined,
    shading: opts.header ? { type: ShadingType.CLEAR, fill: "DCE6F5" } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      children: [new TextRun({ text, bold: !!opts.header, size: 20 })],
    })],
  });
}

function table(headerRow, rows, widths) {
  const w = widths || headerRow.map(() => Math.floor(9600 / headerRow.length));
  return new Table({
    width: { size: 9600, type: WidthType.DXA },
    columnWidths: w,
    rows: [
      new TableRow({ children: headerRow.map((t, i) => cell(t, { header: true, width: w[i] })) }),
      ...rows.map((r) => new TableRow({ children: r.map((t, i) => cell(String(t), { width: w[i] })) })),
    ],
  });
}

const attacksOutput = fs.readFileSync(__dirname + "/captured_output/attacks_output.txt", "utf-8");
const forkOutput = fs.readFileSync(__dirname + "/captured_output/fork_demo.txt", "utf-8");
const pytestOutput = fs.readFileSync(__dirname + "/captured_output/pytest_output.txt", "utf-8");
const syncOutput = fs.readFileSync(__dirname + "/captured_output/sync_three_nodes.txt", "utf-8");

const doc = new Document({
  sections: [
    // ---------- ТИТУЛЬНИЙ АРКУШ ----------
    {
      properties: { page: { size: { width: PAGE_W, height: PAGE_H } } },
      children: [
        new Paragraph({ text: "", spacing: { after: 1200 } }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "Харківський національний університет радіоелектроніки", size: 24 })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 800 },
          children: [new TextRun({ text: "Кафедра програмної інженерії", size: 24 })],
        }),
        new Paragraph({ text: "", spacing: { after: 1600 } }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "ЗВІТ", bold: true, size: 40 })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 200 },
          children: [new TextRun({ text: "до практичного заняття № 1", size: 28 })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 1600 },
          children: [new TextRun({ text: "«Створення власного блокчейну з нуля»", bold: true, size: 30 })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 100 },
          children: [new TextRun({ text: "з дисципліни «Технологія блокчейн та машинне навчання»", size: 22 })],
        }),
        new Paragraph({ text: "", spacing: { after: 2400 } }),
        new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({ text: "Виконала: студентка групи ПЗПІ-23-5", size: 24 })],
        }),
        new Paragraph({
          alignment: AlignmentType.RIGHT,
          spacing: { after: 1600 },
          children: [new TextRun({ text: "Тогтамиш Марія", size: 24 })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "Харків 2026", size: 22 })],
        }),
      ],
    },

    // ---------- ОСНОВНИЙ ЗМІСТ ----------
    {
      properties: { page: { size: { width: PAGE_W, height: PAGE_H } } },
      headers: {
        default: new Header({
          children: [new Paragraph({
            alignment: AlignmentType.RIGHT,
            children: [new TextRun({ text: "Практичне заняття №1 — власний блокчейн", size: 16, italics: true })],
          })],
        }),
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new TextRun({ children: [PageNumber.CURRENT], size: 18 })],
          })],
        }),
      },
      children: [
        h1("1. Мета роботи"),
        p("Мета роботи — на власному коді розібратися, чому дані в блокчейні не можна " +
          "непомітно змінити, як незалежні вузли без жодного центру приходять до однієї " +
          "історії транзакцій і скільки обчислень ця домовленість коштує. Для цього " +
          "реалізовано власну невелику криптовалюту «з нуля»: гаманці з парами ключів, " +
          "підписані транзакції, мемпул, блоки з деревом Меркла, Proof of Work з " +
          "автоматичним коригуванням складності, мережу з кількох вузлів, що " +
          "домовляється про єдину історію транзакцій за принципом «найважчого " +
          "ланцюга», та консольний/REST-інтерфейс керування вузлом."),

        h1("2. Хід роботи та ухвалені рішення"),

        h2("2.1. Гаманець і транзакція"),
        p("Гаманець генерує пару ключів ECDSA на кривій secp256k1 (бібліотека ecdsa — " +
          "готова реалізація самого підпису, дозволена умовою завдання як допоміжна " +
          "криптографічна примітива). Адреса користувача — SHA-256 від публічного ключа."),
        p("Ключове рішення — детермінована серіалізація. Перед підписанням транзакція " +
          "перетворюється на канонічний JSON: ключі словника сортуються (sort_keys=True), " +
          "прибираються зайві пробіли. Це гарантує, що підпис, зроблений на одному вузлі, " +
          "коректно перевіриться на будь-якому іншому, незалежно від порядку полів у " +
          "внутрішньому представленні."),
        p("Поле nonce — порядковий номер транзакції відправника — захищає від повторного " +
          "надсилання (replay) вже підтвердженої транзакції: кожен наступний nonce має " +
          "бути рівно на одиницю більшим за попередній підтверджений."),

        h2("2.2. Мемпул"),
        p("Мемпул виконує чотири перевірки з методички: коректність підпису, достатність " +
          "балансу, правильність nonce, відсутність дублікатів. Найважливіше рішення — " +
          "перевірка балансу враховує НЕ лише підтверджений баланс із ланцюга, а й усі " +
          "транзакції цього ж відправника, які вже лежать у черзі (pending outflow). " +
          "Без цього користувач міг би відправити дві транзакції на весь баланс поспіль, " +
          "і обидві потрапили б у чергу до того, як хоч одна буде підтверджена."),

        h2("2.3. Блок і дерево Меркла"),
        p("Дерево Меркла реалізовано власноруч (файл merkle.py): хеші транзакцій " +
          "попарно об'єднуються знизу вгору, а при непарній кількості елементів на " +
          "рівні останній хеш дублюється. Додатково реалізовано побудову й перевірку " +
          "доказу Меркла (SPV) — шляху хешів-«братів» від листка до кореня, що дозволяє " +
          "«легкому» клієнту переконатись у входженні транзакції в блок, маючи лише " +
          "корінь Меркла із заголовка (додаткове завдання №1)."),

        h2("2.4. Proof of Work і коригування складності"),
        p("Блок вважається знайденим, коли його SHA-256-хеш починається з заданої " +
          "кількості шістнадцяткових нулів (параметр difficulty). Підбір nonce — простий " +
          "повний перебір: саме в цьому й полягає ідея «доказу виконаної роботи» — " +
          "не існує розумнішого способу, ніж пробувати значення одне за одним."),
        p("Коригування складності відбувається кожні K=10 блоків: система порівнює " +
          "фактичний час видобування останніх K блоків з очікуваним (target_block_time × K). " +
          "Якщо блоки знаходились більш ніж удвічі швидше за очікуване — складність " +
          "зростає на 1; якщо повільніше — зменшується на 1 (з обмеженням у межах " +
          "[min_difficulty, max_difficulty])."),

        h2("2.5. Ланцюг і повна перевірка"),
        p("Найважливіша функція проєкту — validate_full_chain() у файлі chain.py. Вона " +
          "проходить усі блоки з нуля і перевіряє: коректність номера блоку, зв'язність " +
          "через previous_hash, відповідність кореня Меркла транзакціям, виконання Proof " +
          "of Work для заявленої складності, коректність усіх підписів, строгу " +
          "послідовність nonce для кожного відправника, відсутність витрат понад баланс " +
          "і те, що винагорода майнера не перевищує base_reward + сума комісій. Будь-яка " +
          "зміна даних у вже доданому блоці ламає щонайменше одну з цих перевірок " +
          "(докладніше — розділ 4 з демонстраціями атак)."),
        p("Ланцюг зберігається у файл через тимчасовий файл + атомарну заміну " +
          "(os.replace), щоб уникнути пошкодження даних при аварійному завершенні " +
          "процесу під час запису."),

        h2("2.6. Мережа вузлів"),
        p("Кожен вузол — окремий процес Flask на своєму порту (blockchain/node.py). " +
          "Вузли обмінюються новими транзакціями (POST /transactions/new) і щойно " +
          "знайденими блоками (POST /blocks/new) через HTTP. Для вибору «правильного» " +
          "ланцюга при розгалуженні використовується НЕ довжина ланцюга, а сумарна " +
          "виконана робота (Σ 16^difficulty за всіма блоками) — це коректніше враховує " +
          "випадки, коли складність по ходу ланцюга змінювалась. Транзакції з блоків, " +
          "що програли розгалуження, автоматично повертаються в мемпул методом " +
          "Mempool.return_transactions()."),

        h2("2.7. Керування вузлом"),
        p("Реалізовано REST API вузла (усі ендпоінти — у node.py) і консольний клієнт " +
          "cli.py, який звертається до цього API: створення гаманця, надсилання " +
          "транзакції, майнінг блоку, перегляд ланцюга/балансу, перевірка ланцюга, " +
          "додавання сусіда, синхронізація з мережею."),

        h2("2.8. Атаки та експеримент"),
        p("Реалізовано й продемонстровано всі п'ять атак з методички (розділ 4) та " +
          "проведено експеримент залежності часу майнінгу від складності (розділ 5)."),

        new Paragraph({ children: [new PageBreak()] }),

        h1("3. Схема модулів"),
        p("Нижче наведено схему залежностей між модулями проєкту. Стрілка «A → B» " +
          "означає «B використовує A» (наприклад, transaction.py використовує " +
          "crypto_utils.py для підпису й хешування)."),
        new Paragraph({
          children: [new ImageRun({
            type: "png",
            data: fs.readFileSync(__dirname + "/figures/module_diagram.png"),
            transformation: { width: 620, height: 397 },
          })],
        }),

        h1("4. Таблиця полів транзакції та блоку"),
        h2("4.1. Транзакція (Transaction)"),
        table(
          ["Поле", "Тип", "Опис"],
          [
            ["sender", "str (hex, 64 симв.)", "Адреса відправника; порожній рядок для coinbase-транзакції"],
            ["recipient", "str (hex, 64 симв.)", "Адреса отримувача"],
            ["amount", "float", "Сума переказу"],
            ["fee", "float", "Комісія, яку забирає майнер"],
            ["nonce", "int", "Порядковий номер транзакції цього відправника"],
            ["timestamp", "float (unix time)", "Час створення транзакції"],
            ["public_key", "str (hex, 128 симв.)", "Публічний ключ відправника (для перевірки підпису)"],
            ["signature", "str (hex, 128 симв.) | null", "ECDSA-підпис над іншими полями; null для coinbase"],
            ["txid", "str (hex, 64 симв.), похідне", "SHA-256 від payload+підпису — ідентифікатор транзакції"],
          ],
          [2200, 2400, 5000]
        ),

        h2("4.2. Заголовок блоку (BlockHeader)"),
        table(
          ["Поле", "Тип", "Опис"],
          [
            ["index", "int", "Номер блоку (0 для генезис-блоку)"],
            ["timestamp", "float (unix time)", "Час створення блоку"],
            ["previous_hash", "str (hex, 64 симв.)", "Хеш попереднього блоку"],
            ["merkle_root", "str (hex, 64 симв.)", "Корінь дерева Меркла над транзакціями блоку"],
            ["difficulty", "int", "Кількість нулів на початку хешу, потрібних для PoW"],
            ["nonce", "int", "Число, яке підбирає майнер під час Proof of Work"],
          ],
          [2200, 2400, 5000]
        ),

        new Paragraph({ children: [new PageBreak()] }),

        h1("5. Фрагменти коду основних модулів"),

        h2("5.1. Детермінована серіалізація (crypto_utils.py)"),
        ...codeBlock(
`def canonical_json(obj):
    """
    Детермінована серіалізація довільного словника в байти.
    Критично для підписів: та сама структура ЗАВЖДИ дає ту саму
    послідовність байтів, незалежно від вузла чи порядку вставки ключів.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True).encode("utf-8")`),

        h2("5.2. Дерево Меркла з обробкою непарної кількості елементів (merkle.py)"),
        ...codeBlock(
`def merkle_root(tx_hashes):
    if not tx_hashes:
        return sha256_hex(b"")
    level = list(tx_hashes)
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])   # дублюємо останній хеш при непарній кількості
        level = [_hash_pair(level[i], level[i+1]) for i in range(0, len(level), 2)]
    return level[0]`),

        h2("5.3. Proof of Work (mining.py)"),
        ...codeBlock(
`def mine_block(block, should_abort=None, max_nonce=2**32):
    block.recompute_merkle_root()
    header = block.header
    nonce = 0
    while nonce <= max_nonce:
        header.nonce = nonce
        if block.meets_difficulty():
            return block
        nonce += 1
    return None`),

        h2("5.4. Вибір найважчого ланцюга при розгалуженні (chain.py)"),
        ...codeBlock(
`def total_work(self):
    """Сумарна робота = сума 16^difficulty по всіх блоках."""
    return sum(16 ** b.header.difficulty for b in self.blocks)

def replace_chain(self, new_blocks):
    candidate = Blockchain(self.params)
    candidate.blocks = new_blocks
    ok, msg = candidate.validate_full_chain()
    if not ok:
        return False, f"Новий ланцюг не пройшов перевірку: {msg}", []
    if candidate.total_work() <= self.total_work():
        return False, "Новий ланцюг не важчий — заміна не потрібна", []
    ...`),

        h2("5.5. Мемпул: облік транзакцій, що вже стоять у черзі (mempool.py)"),
        ...codeBlock(
`pending_outflow = self._pending_outflow(tx.sender)
available = confirmed_balance - pending_outflow
needed = tx.amount + tx.fee
if needed > available + 1e-12:
    raise TransactionRejected(
        f"Недостатньо коштів: потрібно {needed}, доступно {available}")`),

        new Paragraph({ children: [new PageBreak()] }),

        h1("6. Демонстрація п'яти атак"),
        p("Нижче наведено вивід консолі скрипту attacks/demo_attacks.py, який " +
          "послідовно виконує всі п'ять атак і показує реакцію системи на кожну " +
          "(при фактичному захисті цей вивід замінюється реальними скріншотами " +
          "терміналу під час живої демонстрації)."),
        ...codeBlock(attacksOutput.trimEnd()),

        new Paragraph({ children: [new PageBreak()] }),

        h1("7. Синхронізація трьох вузлів і розв'язання розгалуження"),
        h2("7.1. Синхронізація трьох вузлів після майнінгу блоку"),
        p("Блок, намайнений на вузлі A (порт 5001), протягом секунди розповсюджується " +
          "на вузли B (5002) і C (5003) — усі три показують однакову висоту й сумарну " +
          "роботу:"),
        ...codeBlock(syncOutput.trimEnd()),

        h2("7.2. Штучне розгалуження і його розв'язання"),
        p("Вузол C тимчасово ізолюється від мережі (не реєструється як сусід A і B). " +
          "Поки він ізольований, на A і на C майняться РІЗНІ блоки тієї ж висоти — " +
          "з'являється розгалуження. Після повернення C у мережу він викликає " +
          "/nodes/resolve, порівнює сумарну роботу свого ланцюга з ланцюгом сусідів і " +
          "переходить на важчий, а транзакція з його «програного» блоку повертається " +
          "в мемпул:"),
        ...codeBlock(forkOutput.trimEnd()),
        p("Примітка: повернена транзакція в мемпулі C після переходу на новий ланцюг " +
          "виявилась недійсною (0 транзакцій у мемпулі після реорганізації), оскільки " +
          "баланс її відправника в НОВОМУ (виграшному) ланцюзі відрізняється від " +
          "балансу у програному ланцюзі C — типова й очікувана поведінка при " +
          "реорганізації ланцюга."),

        new Paragraph({ children: [new PageBreak()] }),

        h1("8. Експеримент: залежність часу майнінгу від складності"),
        p("Для чотирьох рівнів складності (2, 3, 4, 5 нулів) виконано по 10 незалежних " +
          "запусків майнінгу одного блока (скрипт experiment/measure_difficulty.py). " +
          "Результати:"),
        table(
          ["Складність", "Середній час, с", "Стандартне відхилення, с", "Зростання відносно попередньої"],
          [
            ["2", "0.0012", "0.0016", "—"],
            ["3", "0.0245", "0.0201", "19.67×"],
            ["4", "0.3558", "0.2498", "14.54×"],
            ["5", "4.6251", "3.9878", "13.00×"],
          ],
          [2000, 2600, 2900, 2100]
        ),
        p(""),
        new Paragraph({
          children: [new ImageRun({
            type: "png",
            data: fs.readFileSync(__dirname + "/figures/difficulty_experiment.png"),
            transformation: { width: 560, height: 385 },
          })],
        }),
        h2("Пояснення форми кривої"),
        p("Очікуваний час майнінгу зростає експоненційно зі складністю: кожен " +
          "додатковий шістнадцятковий нуль звужує простір «придатних» хешів у 16 " +
          "разів, а SHA-256 не залишає жодного способу передбачити результат, крім " +
          "повного перебору nonce. Тому на графіку з логарифмічною віссю часу точки " +
          "лягають майже на пряму лінію — ознака експоненційної залежності."),
        p("Конкретні числа: при збільшенні складності з 2 до 3 нулів середній час " +
          "зріс у 19.67 раза, з 3 до 4 — у 14.54 раза, з 4 до 5 — у 13.00 раза, " +
          "що з урахуванням природного розкиду (стандартне відхилення сумірне із " +
          "самим середнім, як і очікується для геометричного розподілу часу очікування " +
          "першого успіху) добре узгоджується з теоретичним множником 16× на кожен " +
          "додатковий шістнадцятковий нуль."),

        new Paragraph({ children: [new PageBreak()] }),

        h1("9. Результат запуску тестів"),
        p("Команда: python3 -m pytest tests/ -v. Реалізовано 36 автоматичних тестів " +
          "(вимога — не менше 12), усі проходять:"),
        ...codeBlock(pytestOutput.trimEnd().split("\n").slice(-20).join("\n")),

        new Paragraph({ children: [new PageBreak()] }),

        h1("10. Таблиця самоперевірки"),
        table(
          ["Пункт", "Виконано", "Де саме видно"],
          [
            ["Генерація ключів, адреса, підпис і перевірка (ECDSA secp256k1)", "так", "crypto_utils.py (KeyPair), wallet.py"],
            ["Детермінована серіалізація транзакцій і заголовка блоку", "так", "crypto_utils.py: canonical_json()"],
            ["Мемпул із 4 перевірками", "так", "mempool.py: add_transaction(); tests/test_mempool.py"],
            ["Блок з усіма полями, SHA-256", "так", "block.py: BlockHeader, Block.hash()"],
            ["Власний корінь Меркла з тестами на парну/непарну кількість", "так", "merkle.py; tests/test_merkle.py"],
            ["Proof of Work з параметром складності", "так", "mining.py: mine_block()"],
            ["Coinbase-винагорода з урахуванням комісій", "так", "chain.py: build_candidate_block()"],
            ["Автоматичне коригування складності кожні K блоків", "так", "difficulty.py: adjust_difficulty()"],
            ["Генезис-блок, додавання блоків, баланси", "так", "block.py: genesis(); chain.py: append_block()"],
            ["Збереження у файл і відновлення після перезапуску", "так", "chain.py: save()/load(); tests/test_chain.py"],
            ["Повна перевірка ланцюга за всіма правилами", "так", "chain.py: validate_full_chain()"],
            ["Не менше 3 вузлів, обмін транзакціями й блоками", "так", "node.py; розділ 7.1 звіту"],
            ["Вибір ланцюга з найбільшою роботою на штучному розгалуженні", "так", "chain.py: total_work(), replace_chain(); розділ 7.2"],
            ["Транзакції з відкинутих блоків повертаються в мемпул", "так", "mempool.py: return_transactions(); розділ 7.2"],
            ["Консольний інтерфейс/REST API з усіма командами кроку 7", "так", "cli.py, node.py (create_app)"],
            ["5 атак відбито", "так", "attacks/demo_attacks.py; tests/test_chain.py; розділ 6"],
            ["Не менше 12 тестів, усі проходять", "так (36 тестів)", "tests/*; розділ 9"],
            ["Вимірювання часу майнінгу, 4 рівні, ≥10 запусків", "так", "experiment/measure_difficulty.py; розділ 8"],
            ["Графік з логарифмічною віссю та поясненням", "так", "experiment/difficulty_experiment.png; розділ 8"],
            ["README із запуском трьох вузлів", "так", "README.md"],
          ],
          [5200, 1400, 3000]
        ),

        new Paragraph({ children: [new PageBreak()] }),

        h1("11. Висновки"),
        p("У межах роботи реалізовано власну спрощену криптовалюту без використання " +
          "готових блокчейн-фреймворків. Практично підтверджено ключові властивості " +
          "блокчейну:"),
        bullet("Незмінність історії забезпечується ланцюжком хешів і деревом Меркла: " +
          "зміна одного байта в транзакції старого блоку (експеримент у розділі 6, атака 1) " +
          "змінює корінь Меркла цього блоку й виявляється повною перевіркою ланцюга; " +
          "навіть якщо зловмисник перемайновує змінений блок (атака 2), розривається " +
          "зв'язок previous_hash із наступним блоком."),
        bullet("Складність підбору nonce зростає експоненційно: збільшення складності " +
          "з 2 до 5 шістнадцяткових нулів (крок у 3 одиниці) підвищило середній час " +
          "майнінгу з 0.0012 до 4.63 секунди — приблизно у 3900 разів, що узгоджується " +
          "з теоретичним очікуванням 16³ ≈ 4096."),
        bullet("Децентралізований консенсус за принципом «найважчого ланцюга» " +
          "(розділ 7.2) дозволяє незалежним вузлам без центрального координатора " +
          "дійти згоди щодо єдиної історії транзакцій навіть після тимчасового " +
          "розгалуження мережі, при цьому транзакції з програної гілки коректно " +
          "повертаються в чергу на повторний розгляд."),
        bullet("Усі п'ять досліджених атак (підміна суми, підміна з перемайнінгом, " +
          "підроблений підпис, подвійна витрата, повторне надсилання) успішно " +
          "відбиваються комбінацією перевірок підпису, дерева Меркла, зв'язності " +
          "ланцюга та обліку резервованих коштів у мемпулі."),
        p("Разом з тим реалізація має відомі обмеження (навмисно, як навчальний " +
          "прототип): відсутній захист від атаки 51% (окрім самого факту, що вона " +
          "вимагає контролю над більшістю обчислювальної потужності мережі — " +
          "додаткове завдання щодо симуляції цієї атаки в межах поточної роботи не " +
          "виконувалось); мережевий шар використовує розробний сервер Flask, " +
          "непридатний для промислового навантаження; відсутнє шифрування зв'язку " +
          "між вузлами (HTTP, не HTTPS)."),

        h1("12. Посилання на проєкт"),
        p("Репозиторій проєкту на GitHub: [ВКАЗАТИ ПОСИЛАННЯ ПІСЛЯ ПУБЛІКАЦІЇ " +
          "РЕПОЗИТОРІЮ]", { italics: true }),
        p("Приватні ключі гаманців та файли стану ланцюга (chain_*.json) до " +
          "репозиторію не потрапляють (див. .gitignore)."),
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(__dirname + "/Звіт_практичне_заняття_1_блокчейн.docx", buf);
  console.log("OK, written");
});
