const app = document.querySelector('#app');
const user = {
  id: window.Telegram?.WebApp?.initDataUnsafe?.user?.id?.toString() || 'demo-user',
  name: window.Telegram?.WebApp?.initDataUnsafe?.user?.first_name || 'Гость',
};
const state = { view: 'home', movie: null, session: null, seats: [], taken: [] };
const api = (path, options = {}) => fetch(`/api${path}`, {
  headers: { 'Content-Type': 'application/json' }, ...options,
}).then(async response => {
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || 'Произошла ошибка');
  return data;
});
const toast = message => { const node = document.querySelector('#toast'); node.textContent = message; node.style.display = 'block'; setTimeout(() => { node.style.display = 'none'; }, 2600); };

function render() {
  document.querySelectorAll('nav button').forEach(button => button.classList.toggle('active', button.dataset.view === state.view));
  ({ home, detail, booking, tickets, about, admin }[state.view] || home)();
}

async function home() {
  const movies = await api('/movies');
  app.innerHTML = `<section class="hero"><span class="muted">Сегодня в прокате</span><h1>Найди свой<br><span style="color:var(--accent)">идеальный фильм</span></h1></section>
    <div class="filters"><button class="chip active">Все фильмы</button><button class="chip">Премьеры</button><button class="chip">Скоро</button></div>
    <div class="grid">${movies.map(movie => `<article class="movie-card" onclick="openMovie(${movie.id})"><img src="${movie.poster}" loading="lazy"><div class="content"><h3>${movie.title}</h3><div class="rating">★ ${movie.rating} <span class="tag"> · ${movie.genre}</span></div></div></article>`).join('')}</div>`;
}

async function openMovie(id) { state.movie = await api(`/movies/${id}`); state.view = 'detail'; render(); }

async function detail() {
  const movie = state.movie;
  app.innerHTML = `<section class="detail"><button class="back" onclick="state.view='home';render()">← Назад к афише</button><img src="${movie.poster}"><h1>${movie.title}</h1>
    <span class="muted">${movie.genre} · ${movie.duration} мин · ${movie.age}+</span><div class="stats"><span class="stat">★ Nova ${movie.rating}</span><span class="stat">IMDb ${movie.imdb}</span><span class="stat">КиноПоиск ${movie.kinopoisk}</span></div>
    <p class="muted">${movie.description}</p><a href="${movie.trailer}" target="_blank" rel="noreferrer">▶ Смотреть трейлер на YouTube</a><h2>Выберите сеанс</h2>
    <div class="sessions">${movie.sessions.map(session => `<button class="session" onclick="startBooking('${session}')">${session}</button>`).join('')}</div><h2>Отзывы</h2>
    ${movie.reviews.length ? movie.reviews.map(review => `<div class="review"><b>${review.user_name}</b> <span class="rating">★ ${review.rating}</span><p class="muted">${review.text}</p></div>`).join('') : '<p class="muted">Пока нет отзывов. Будьте первым!</p>'}
    <div class="card"><b>Оставить отзыв</b><input class="input" id="reviewText" maxlength="1000" placeholder="Расскажите о фильме"><select class="input" id="reviewRating"><option value="5">★★★★★</option><option value="4">★★★★</option><option value="3">★★★</option><option value="2">★★</option><option value="1">★</option></select><button class="primary" onclick="sendReview()">Опубликовать</button></div></section>`;
}

async function sendReview() {
  const text = document.querySelector('#reviewText').value.trim();
  if (text.length < 3) return toast('Напишите отзыв подробнее');
  try { await api('/reviews', { method: 'POST', body: JSON.stringify({ user_id: user.id, user_name: user.name, movie_id: state.movie.id, rating: Number(document.querySelector('#reviewRating').value), text }) }); toast('Отзыв опубликован'); state.movie = await api(`/movies/${state.movie.id}`); render(); } catch (error) { toast(error.message); }
}

async function startBooking(session) { state.session = session; const data = await api(`/sessions/${state.movie.id}/${session}/seats`); state.taken = data.taken; state.seats = []; state.view = 'booking'; render(); }
function toggleSeat(id) { if (state.seats.includes(id)) state.seats = state.seats.filter(seat => seat !== id); else if (state.seats.length < 6) state.seats.push(id); else return toast('Можно выбрать до 6 мест'); render(); }
function booking() {
  const seats = []; for (let row = 1; row <= 8; row += 1) for (let col = 1; col <= 10; col += 1) { const id = `${row}-${col}`; const status = state.taken.includes(id) ? 'taken' : state.seats.includes(id) ? 'selected' : ''; seats.push(`<button class="seat ${status}" ${status === 'taken' ? 'disabled' : ''} onclick="toggleSeat('${id}')">${col}</button>`); }
  app.innerHTML = `<section><button class="back" onclick="state.view='detail';render()">← ${state.movie.title} · ${state.session}</button><h1>Выберите места</h1><p class="muted">Экран</p><div style="height:4px;background:linear-gradient(90deg,transparent,var(--accent),transparent);margin:12px 20px 30px"></div><div class="seat-grid">${seats.join('')}</div><p class="muted">Выбрано: ${state.seats.join(', ') || '—'} · ${(state.seats.length * 30000).toLocaleString()} сум</p><input class="input" id="promo" maxlength="30" placeholder="Промокод (необязательно)"><button class="primary" onclick="book()">Забронировать</button></section>`;
}
async function book() { if (!state.seats.length) return toast('Выберите хотя бы одно место'); try { const result = await api('/bookings', { method: 'POST', body: JSON.stringify({ user_id: user.id, user_name: user.name, movie_id: state.movie.id, session: state.session, seats: state.seats, promo: document.querySelector('#promo').value }) }); toast(`Бронирование ${result.code} подтверждено`); state.view = 'tickets'; render(); } catch (error) { toast(error.message); } }

async function tickets() { const [bookings, notifications] = await Promise.all([api(`/me/${user.id}/bookings`), api(`/me/${user.id}/notifications`)]); app.innerHTML = `<h1>Мои билеты</h1>${notifications.length ? `<div class="card"><b>Уведомления</b>${notifications.slice(0, 3).map(note => `<p class="muted">${note.message}</p>`).join('')}</div>` : ''}${bookings.length ? bookings.map(ticket => `<div class="card"><b>${ticket.movie}</b><p class="muted">${ticket.session} · места ${ticket.seats.join(', ')}</p><strong>${ticket.total.toLocaleString()} сум</strong><p>Код: <code>${ticket.code}</code></p></div>`).join('') : '<div class="empty">У вас пока нет бронирований</div>'}`; }
async function about() { const info = await api('/about'); app.innerHTML = `<h1>О кинотеатре</h1><div class="card"><h2>${info.name}</h2><p class="muted">${info.address}</p><p>${info.phone}<br>${info.hours}</p><a href="https://maps.google.com/?q=${info.coordinates.lat},${info.coordinates.lng}" target="_blank" rel="noreferrer">Открыть карту →</a></div><h2>Галерея</h2><div class="grid">${info.gallery.map(image => `<img class="movie-card" src="${image}" loading="lazy">`).join('')}</div>`; }

async function admin() {
  app.innerHTML = '<h1>Админ-панель</h1><p class="muted">Введите Telegram ID администратора для просмотра статистики.</p><input class="input" id="adminId" placeholder="ADMIN_IDS"><button class="primary" onclick="loadAdmin()">Войти</button>';
}
async function loadAdmin() {
  const id = document.querySelector('#adminId').value.trim();
  try { const headers = { 'X-Admin-Id': id }; const [overview, bookings, reviews] = await Promise.all(['/admin/overview', '/admin/bookings', '/admin/reviews'].map(path => api(path, { headers }))); app.innerHTML = `<h1>Админ-панель</h1><div class="stats"><span class="stat">Фильмов: ${overview.movies}</span><span class="stat">Бронирований: ${overview.bookings}</span><span class="stat">Выручка: ${overview.revenue.toLocaleString()} сум</span><span class="stat">Отзывов: ${overview.reviews}</span></div><h2>Последние бронирования</h2>${bookings.length ? bookings.slice(0, 10).map(item => `<div class="card"><b>${item.code}</b><p class="muted">${item.user_name} · ${item.seats} · ${item.total.toLocaleString()} сум</p></div>`).join('') : '<p class="muted">Бронирований нет</p>'}<h2>Отзывы</h2>${reviews.length ? reviews.slice(0, 10).map(item => `<div class="card"><b>${item.user_name} · ★ ${item.rating}</b><p class="muted">${item.text}</p></div>`).join('') : '<p class="muted">Отзывов нет</p>'}`; } catch (error) { toast(error.message); }
}

document.querySelectorAll('nav button').forEach(button => { button.onclick = () => { state.view = button.dataset.view; render(); }; });
document.querySelector('#profileBtn').onclick = () => { state.view = 'tickets'; render(); };
window.Telegram?.WebApp?.ready(); window.Telegram?.WebApp?.expand(); render();
