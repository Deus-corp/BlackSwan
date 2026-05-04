// theme/js/sidebar.js
document.addEventListener('DOMContentLoaded', function() {
    // В mdBook боковая панель – это <nav> с вложенными списками
    const nav = document.querySelector('nav[role="navigation"]');
    if (!nav) return;

    // Ищем все элементы с подпунктами (где есть вложенный <ol> или <ul>)
    const parentItems = nav.querySelectorAll('li.chapter-item');
    parentItems.forEach(function(li) {
        const sublist = li.querySelector('ol, ul');
        if (!sublist) return;

        // Ссылка внутри родительского пункта
        const link = li.querySelector('a');
        if (!link) return;

        // Добавляем класс для стилизации
        link.classList.add('expandable');

        // Сворачиваем вложенный список по умолчанию
        sublist.style.maxHeight = '0px';
        sublist.style.overflow = 'hidden';
        sublist.style.transition = 'max-height 0.3s ease';

        // Если текущая страница находится внутри подменю – раскрываем его сразу
        if (sublist.querySelector('.active')) {
            sublist.style.maxHeight = sublist.scrollHeight + 'px';
            link.classList.add('open');
        }

        // Обработчик клика
        link.addEventListener('click', function(e) {
            // Если у ссылки есть URL, предотвращаем переход
            if (link.getAttribute('href') && link.getAttribute('href') !== '#') {
                // Разрешаем переход, но не сворачиваем меню
            } else {
                e.preventDefault();
            }
            const isOpen = link.classList.contains('open');
            if (isOpen) {
                sublist.style.maxHeight = '0px';
                link.classList.remove('open');
            } else {
                sublist.style.maxHeight = sublist.scrollHeight + 'px';
                link.classList.add('open');
            }
        });
    });
});