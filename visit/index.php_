<?php
require_once 'data.php';
$role = $_GET['role'] ?? 'engineer';
$lang = $_GET['lang'] ?? 'ru';

ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

// Валидация
if (!isset($content[$role])) $role = 'engineer';
if (!isset($content[$role][$lang])) $lang = 'ru';
$page = $content[$role][$lang];
?>
<!DOCTYPE html>
<html lang="<?= $lang ?>">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?= $page['title'] ?> | Portfolio</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, sans-serif; margin: 0; display: flex; height: 100vh; background: #f4f7f6; color: #333; }
        .sidebar { width: 320px; background: #fff; border-right: 1px solid #e0e0e0; display: flex; flex-direction: column; padding: 40px 20px; box-shadow: 2px 0 15px rgba(0,0,0,0.05); }
        .avatar { width: 160px; height: 160px; border-radius: 50%; object-fit: cover; border: 4px solid #007bff; margin: 0 auto 25px; }
        .name { text-align: center; font-size: 1.5em; font-weight: bold; margin-bottom: 30px; }
        .nav-menu { flex-grow: 1; }
        .nav-item { display: block; padding: 12px 15px; text-decoration: none; color: #666; border-radius: 8px; margin-bottom: 10px; transition: 0.3s; font-weight: 500; }
        .nav-item:hover { background: #f0f7ff; color: #007bff; }
        .nav-item.active { background: #007bff; color: #fff; }
        .lang-switch { display: flex; gap: 10px; border-top: 1px solid #eee; padding-top: 20px; }
        .lang-btn { flex: 1; text-align: center; padding: 8px; text-decoration: none; color: #333; border: 1px solid #ddd; border-radius: 5px; font-size: 0.85em; }
        .lang-btn.active { border-color: #007bff; color: #007bff; font-weight: bold; }
        .main { flex-grow: 1; padding: 60px; overflow-y: auto; display: flex; flex-direction: column; }
        .marketing-header { font-size: 2.2em; color: #007bff; margin-bottom: 20px; font-weight: 800; line-height: 1.2; }
        .story-text { font-size: 1.15em; line-height: 1.7; color: #444; max-width: 700px; margin-bottom: 40px; }
        .btn-github { display: inline-block; background: #24292e; color: white; padding: 15px 30px; text-decoration: none; border-radius: 6px; font-weight: 600; transition: 0.3s; margin-bottom: 20px; }
        .btn-github:hover { background: #444; transform: translateY(-2px); }
        .pdf-link { color: #888; text-decoration: none; font-size: 0.9em; border-bottom: 1px dashed #ccc; align-self: flex-start; }
    </style>
</head>
<body>

<aside class="sidebar">
    <img src="avatar.jpg" alt="Photo" class="avatar">
    <div class="name">Андрей Иванов</div>
    
    <nav class="nav-menu">
        <a href="?role=python&lang=<?= $lang ?>" class="nav-item <?= $role=='python'?'active':'' ?>">Python / AI</a>
        <a href="?role=cpp&lang=<?= $lang ?>" class="nav-item <?= $role=='cpp'?'active':'' ?>">C++ / Systems</a>
        <a href="?role=engineer&lang=<?= $lang ?>" class="nav-item <?= $role=='engineer'?'active':'' ?>">Systems Engineer</a>
    </nav>

    <div class="lang-switch">
        <a href="?role=<?= $role ?>&lang=ru" class="lang-btn <?= $lang=='ru'?'active':'' ?>">RU</a>
        <a href="?role=<?= $role ?>&lang=en" class="lang-btn <?= $lang=='en'?'active':'' ?>">EN</a>
    </div>
</aside>

<main class="main">
    <div class="marketing-header"><?= $page['marketing'] ?></div>
    <div class="story-text"><?= $page['story'] ?></div>
    
    <a href="<?= $page['github'] ?>" class="btn-github" target="_blank"><?= $page['cta'] ?> →</a>
    
    <a href="<?= $page['pdf'] ?>" class="pdf-link" target="_blank">
        <?= $lang=='ru' ? 'Скачать полное резюме для фактов (PDF)' : 'Download full resume for facts (PDF)' ?>
    </a>
</main>

</body>
</html>