/* ==============================================
   BUNDLBITE MVP — Interaction Logic
   Mock AI responses to demonstrate the UX flow.
   Replace with real LangChain + MCP calls in v2.
   ============================================== */

(function () {
  // --- Theme toggle ---
  const toggle = document.querySelector('[data-theme-toggle]');
  const root = document.documentElement;
  let theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  root.setAttribute('data-theme', theme);
  toggle.textContent = theme === 'dark' ? '☀' : '☾';
  toggle.addEventListener('click', () => {
    theme = theme === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', theme);
    toggle.textContent = theme === 'dark' ? '☀' : '☾';
  });

  // --- Quick fill examples ---
  window.fillExample = function (n) {
    const examples = {
      1: 'We are 5 people. Rahul wants chicken biryani, Sneha wants masala dosa, Ajay wants a chicken burger, Priya wants a paneer macro bowl, Vikram wants steamed momos. Total budget is ₹1200.',
      2: 'Late night for 3. One wants a margherita pizza, one wants fried rice with chicken, one wants momos. Keep it under ₹700.',
      3: 'Group of 4. Two are vegetarian. One wants a paneer wrap, one wants a veggie burger, one wants chicken shawarma, one wants mutton biryani. Budget ₹1000. Prefer high-rated places only.'
    };
    document.getElementById('chatInput').value = examples[n];
  };

  // --- Mock basket data ---
  const MOCK_BASKETS = [
    {
      label: 'Basket A · Swiggy blend',
      restaurants: 'Paradise Biryani + Udupi Tiffins + Burger Hub',
      rating: '4.3',
      items: [
        ['Chicken biryani', '₹249'],
        ['Masala dosa', '₹159'],
        ['Chicken burger meal', '₹209'],
        ['Paneer protein bowl', '₹229'],
        ['Steamed momos', '₹139'],
        ['Taxes + platform + delivery', '₹163'],
      ],
      total: 1148,
      budget: 1200,
      eta: '27',
      avgRating: '4.3',
    },
    {
      label: 'Basket B · Zomato blend',
      restaurants: 'Meghana Foods + Taaza Kitchen + Bowl Theory',
      rating: '4.6',
      items: [
        ['Chicken biryani', '₹269'],
        ['Ghee podi dosa', '₹169'],
        ['Smash chicken burger', '₹229'],
        ['Paneer macro bowl', '₹239'],
        ['Veg momos', '₹129'],
        ['Taxes + platform + delivery', '₹158'],
      ],
      total: 1193,
      budget: 1200,
      eta: '20',
      avgRating: '4.6',
    },
  ];

  function renderBasket(b) {
    return `
      <article class="restaurant-card">
        <div class="restaurant-top">
          <div>
            <strong>${b.label}</strong>
            <p class="muted">${b.restaurants}</p>
          </div>
          <span class="score">${b.rating} ★</span>
        </div>
        ${b.items.map(([name, price]) =>
          `<div class="menu-line"><span>${name}</span><strong>${price}</strong></div>`
        ).join('')}
        <div style="margin-top:4px;">
          <button class="btn btn-secondary" style="width:100%;font-size:var(--text-xs);" onclick="selectBasket(${JSON.stringify(b).replace(/'/g, "'")})">Select this basket</button>
        </div>
      </article>`;
  }

  window.selectBasket = function (b) {
    document.getElementById('totalPrice').textContent = `₹${b.total.toLocaleString('en-IN')}`;
    const saved = b.budget - b.total;
    document.getElementById('savingNote').textContent = saved >= 0 ? `₹${saved} saved against group cap.` : `₹${Math.abs(saved)} over budget.`;
    const pct = Math.min(100, Math.round((b.total / b.budget) * 100));
    document.getElementById('budgetPct').textContent = pct + '%';
    document.getElementById('progressBar').style.width = pct + '%';
    document.getElementById('placeOrderBtn').disabled = false;
    simulateTracking();
  };

  function simulateTracking() {
    const dots = ['t1', 't2', 't3', 't4', 't5'];
    const classes = ['active', 'active', 'pending', '', ''];
    dots.forEach((id, i) => {
      const el = document.getElementById(id);
      el.className = 'dot ' + (classes[i] || '');
    });
  }

  function addBubble(text, role, chips) {
    const thread = document.getElementById('chatThread');
    const div = document.createElement('div');
    div.className = `bubble ${role}`;
    div.innerHTML = `<div>${text}</div>`;
    if (chips && chips.length) {
      const row = document.createElement('div');
      row.className = 'chip-row';
      chips.forEach(c => {
        const span = document.createElement('span');
        span.className = 'choice-chip';
        span.textContent = c;
        row.appendChild(span);
      });
      div.appendChild(row);
    }
    const meta = document.createElement('span');
    meta.className = 'bubble-meta';
    meta.textContent = role === 'user' ? 'You · Just now' : 'Bundlbite AI · Just now';
    div.appendChild(meta);
    thread.appendChild(div);
    thread.scrollTop = thread.scrollHeight;
  }

  function showResults(baskets) {
    const area = document.getElementById('basketArea');
    area.innerHTML = baskets.map(renderBasket).join('');
    document.getElementById('statFit').textContent = '96%';
    document.getElementById('statRating').textContent = '4.4 ★';
    document.getElementById('statEta').textContent = '27m';
  }

  // --- Send button ---
  document.getElementById('sendBtn').addEventListener('click', () => {
    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    if (!text) return;
    addBubble(text, 'user');
    input.value = '';
    setTimeout(() => {
      addBubble(
        'Got it — I parsed 5 preferences and a ₹1,200 budget. Querying Swiggy and Zomato via MCP… comparing by price, rating, and ETA.',
        'assistant'
      );
      setTimeout(() => {
        addBubble(
          'Found two baskets that fit your budget. Basket A is cheapest (₹1,148). Basket B has better ratings and a faster ETA. Pick one to proceed.',
          'assistant',
          ['Basket A · ₹1,148 · Swiggy', 'Basket B · ₹1,193 · Zomato', 'Best value overall']
        );
        showResults(MOCK_BASKETS);
      }, 1200);
    }, 700);
  });

  // --- Optimise button ---
  document.getElementById('optimiseBtn').addEventListener('click', () => {
    addBubble('Running price optimisation across both providers…', 'assistant');
    setTimeout(() => {
      addBubble(
        'Optimised! I swapped one combo meal to save ₹52 without changing any preference match. Preference score: 9.1/10.',
        'assistant',
        ['Price optimised · ₹1,148', 'Rating weighted', 'RAG match: 82%']
      );
      showResults(MOCK_BASKETS);
    }, 900);
  });
})();
