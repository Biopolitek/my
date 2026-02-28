<!DOCTYPE html>
<html lang="<?= $lang ?>">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?= $item['title'] ?> | Portfolio</title>
    <!-- Подключаем современный шрифт -->
    <link href="https://fonts.googleapis.com" rel="stylesheet">
    <style>
        :root { --primary: #007bff; --dark: #1a1a1a; --gray: #666; --bg: #fdfdfd; }
        * { box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; margin: 0; display: flex; height: 100vh; background: var(--bg); color: var(--dark); overflow: hidden; }

        /* Боковая панель (Личный бренд) */
        .sidebar { width: 340px; background: #fff; border-right: 1px solid #eee; display: flex; flex-direction: column; padding: 50px 30px; box-shadow: 10px 0 30px rgba(0,0,0,0.02); }
        .avatar { width: 200px; height: 200px; border-radius: 50%; object-fit: cover; border: 6px solid var(--primary); margin: 0 auto 30px; box-shadow: 0 10px 20px rgba(0,123,255,0.2); }
        .name { text-align: center; font-size: 1.6rem; font-weight: 800; margin-bottom: 40px; letter-spacing: -0.5px; }
        
        .nav-group { flex-grow: 1; }
        .nav-btn { display: block; padding: 15px 20px; margin-bottom: 10px; text-decoration: none; color: var(--gray); border-radius: 12px; transition: all 0.3s; font-weight: 500; border: 1px solid transparent; }
        .nav-btn:hover { background: #f8f9fa; color: var(--primary); }
        .nav-btn.active { background: #eef6ff; color: var(--primary); border-color: rgba(0,123,255,0.1); font-weight: 700; }

        .lang-switch { display: flex; gap: 10px; border-top: 1px solid #f0f0f0; padding-top: 30px; justify-content: center; }
        .lang-btn { text-decoration: none; color: #999; font-weight: 700; font-size: 0.9rem; padding: 5px 15px; border-radius: 6px; transition: 0.2s; }
        .lang-btn.active { color: var(--primary); background: #eef6ff; }

        /* Основной контент (Маркетинг и Кейсы) */
        .main { flex-grow: 1; padding: 80px; display: flex; flex-direction: column; justify-content: center; max-width: 900px; overflow-y: auto; }
        .hero-title { font-size: 3.5rem; font-weight: 800; margin-bottom: 25px; line-height: 1.1; color: var(--dark); letter-spacing: -1.5px; }
        .story { font-size: 1.3rem; line-height: 1.7; color: #444; margin-bottom: 50px; font-weight: 300; }
        .story b { color: var(--primary); font-weight: 700; }

        .actions { display: flex; align-items: center; gap: 30px; }
        .github-btn { background: var(--dark); color: #fff; padding: 18px 35px; border-radius: 40px; text-decoration: none; font-weight: 700; transition: 0.3s; display: flex; align-items: center; gap: 10px; box-shadow: 0 10px 20px rgba(0,0,0,0.1); }
        .github-btn:hover { transform: translateY(-3px); box-shadow: 0 15px 25px rgba(0,0,0,0.15); background: #333; }
        
        .pdf-link { font-size: 0.9rem; color: #aaa; text-decoration: none; border-bottom: 1px solid #eee; transition: 0.2s; }
        .pdf-link:hover { color: var(--primary); border-color: var(--primary); }

        /* Адаптив для мобилок */
        @media (max-width: 900px) {
            body { flex-direction: column; height: auto; overflow: visible; }
            .sidebar { width: 100%; height: auto; border-right: none; border-bottom: 1px solid #eee; padding: 30px; }
            .main { padding: 40px 20px; text-align: center; }
            .hero-title { font-size: 2.5rem; }
            .actions { flex-direction: column; }
        }
    </style>
</head>
<body>

    <aside class="sidebar">
        <!-- Твое фото: avatar.jpg -->
        <img src="avatar.jpg" alt="Andrey Ivanov" class="avatar">
        
        <div class="name">Андрей Иванов</div>

        <nav class="nav-group">
            <a href="?role=python&lang=<?= $lang ?>" class="nav-btn <?= $role=='python'?'active':'' ?>">Python / AI Automation</a>
            <a href="?role=cpp&lang=<?= $lang ?>" class="nav-btn <?= $role=='cpp'?'active':'' ?>">C++ / System Architect</a>
            <a href="?role=engineer&lang=<?= $lang ?>" class="nav-btn <?= $role=='engineer'?'active':'' ?>">Systems Engineer (L3)</a>
        </nav>
        
        <div class="lang-switch">
            <a href="?role=<?= $role ?>&lang=ru" class="lang-btn <?= $lang=='ru'?'active':'' ?>">RU</a>
            <a href="?role=<?= $role ?>&lang=en" class="lang-btn <?= $lang=='en'?'active':'' ?>">EN</a>
        </div>
    </aside>

    <main class="main">
        <h1 class="hero-title"><?= $item['title'] ?></h1>
        
        <div class="story">
            <?= $item['story'] ?>
        </div>
        
        <div class="actions">
            <a href="<?= $item['github'] ?>" target="_blank" class="github-link github-btn">
                <svg height="24" width="24" viewBox="0 0 16 16" fill="white"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>
                <?= $item['cta_github'] ?>
            </a>

            <a href="<?= $item['pdf'] ?>" target="_blank" class="pdf-link">
                <?= $lang=='ru' ? 'Верифицировать опыт (Скачать PDF)' : 'Verify Background (Download PDF)' ?>
            </a>
        </div>
    </main>

</body>
</html>