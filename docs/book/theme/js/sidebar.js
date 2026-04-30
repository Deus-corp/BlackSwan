document.addEventListener('DOMContentLoaded', function() {
    const active = document.querySelector('.sidebar .active');
    if (!active) return;
    let parent = active.parentElement;
    while (parent && parent.classList.contains('sidebar-section')) {
        parent.classList.add('open');
        parent = parent.parentElement;
    }
});
