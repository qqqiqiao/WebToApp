/* WebToApp notices.
   This is the only place a notice is written. The page draws them as a
   timeline under the header. It does not open a dialog.

   To add one: put a new object at the top of NOTICES (newest first).
   publishedAt is UTC, ISO-8601. Give title and paragraphs for every
   language in CHROME's list. Missing text falls back to English, then
   Chinese. Keep paragraphs as short sentences. */
(function () {
  'use strict';

  var LANGS = ['en', 'zh', 'ja', 'ar', 'ru', 'es', 'pt', 'fr', 'de'];

  var CHROME = {
    en: { kicker: 'Notices', heading: 'What changed' },
    zh: { kicker: '公告', heading: '站点通知' },
    ja: { kicker: 'お知らせ', heading: '変更のお知らせ' },
    ar: { kicker: 'إعلانات', heading: 'ما الذي تغيّر' },
    ru: { kicker: 'Объявления', heading: 'Что изменилось' },
    es: { kicker: 'Avisos', heading: 'Qué cambió' },
    pt: { kicker: 'Avisos', heading: 'O que mudou' },
    fr: { kicker: 'Annonces', heading: 'Ce qui a changé' },
    de: { kicker: 'Hinweise', heading: 'Was sich geändert hat' }
  };

  var NOTICES = [
    {
      id: '2026-10-13-market-icons',
      publishedAt: '2026-10-13T16:00:00Z',
      title: {
        en: 'Market cleanup: duplicate apps and flat icons',
        zh: '市场整理：重复应用和纯色图标',
        ja: '市場の整理：重複アプリと単色アイコン',
        ar: 'ترتيب السوق: التطبيقات المكررة والأيقونات أحادية اللون',
        ru: 'Разбор рынка: дубликаты и однотонные значки',
        es: 'Limpieza del mercado: apps repetidas e iconos planos',
        pt: 'Limpeza do mercado: apps repetidos e ícones chapados',
        fr: 'Rangement du marché : doublons et icônes unies',
        de: 'Markt aufgeräumt: doppelte Apps und flache Symbole'
      },
      paragraphs: {
        en: [
          'On 13 October 2026 we tidied the public market.',
          'When one person had several public apps with the same name, the same address, the same uploaded icon, or the same page content, we kept only the newest. The earlier ones have left the market. Their download links still open, and we are not putting those copies back.',
          'An icon that is 90% one color, including a near-purple block, cannot be used. We removed those pictures. The white square on a card is the empty icon slot, not a white icon we drew.',
          'If your app is still listed and the icon slot is empty, rebuild it with a picture that has a real design before 20 October 2026, 16:00 UTC. If it is still empty or still a flat color then, the app leaves the market. A flat icon found later gets the same seven days from the day we notice it.'
        ],
        zh: [
          '2026年10月13日，我们整理了公开市场。',
          '同一个人名下，名字、网址、自己上传的图标或页面内容相同的应用，只保留最新的一条。更早的那些已经退出市场，下载链接还能打开，这次不会再放回去。',
          '一种颜色占到画面 90% 以上的图标不能用，接近纯紫的色块也算。这些图已经拿掉。卡片上的白块是空出来的图标位置，不是我们换成了白色图标。',
          '图标被拿掉、应用还在市场上的，请在 2026年10月20日 16:00（UTC）前重新生成，换上一张有图案的图。到那时如果还是空的，或者仍是这种纯色图，应用会退出市场。以后新发现的纯色图标，从发现那天起同样给 7 天。'
        ],
        ja: [
          '2026年10月13日、公開市場を整理しました。',
          '同じ人が出した公開アプリで、名前・アドレス・アップロードしたアイコン・ページ内容が同じものは、いちばん新しい一つだけ残しました。それより前のものは市場から外れています。ダウンロードリンクは開きます。戻す予定はありません。',
          '画面の90%以上が一つの色のアイコンは使えません。紫に近いベタ塗りも同じです。その画像は外しました。カードの白い四角は空いた枠で、白いアイコンに描き替えたのではありません。',
          'アイコンが外れたまま市場に残っているアプリは、2026年10月20日 16:00（UTC）までに、模様のある画像で作り直してください。その時点で空のまま、または単色のままだと市場から外れます。このあと見つかった単色アイコンも、見つかった日から7日です。'
        ],
        ar: [
          'في 13 أكتوبر 2026 رتّبنا السوق العام.',
          'إذا نشر الشخص نفسه عدة تطبيقات عامة بالاسم نفسه أو العنوان نفسه أو الأيقونة المرفوعة نفسها أو المحتوى نفسه، أبقينا الأحدث فقط. الأقدم خرج من السوق. رابط التنزيل ما زال يفتح، ولن نعيد تلك النسخ.',
          'الأيقونة التي يشغل لون واحد 90% من صورتها لا تُستخدم، بما في ذلك الكتلة القريبة من البنفسجي. أزلنا هذه الصور. المربع الأبيض على البطاقة مكان فارغ، وليس أيقونة بيضاء رسمناها.',
          'إذا بقي تطبيقك في السوق وخانة الأيقونة فارغة، أعد بناءه بصورة فيها رسم قبل 20 أكتوبر 2026 الساعة 16:00 بالتوقيت العالمي. إن بقيت فارغة أو بلون واحد عندها، يخرج التطبيق من السوق. أي أيقونة مسطحة نكتشفها لاحقًا تأخذ الأيام السبعة نفسها من يوم اكتشافها.'
        ],
        ru: [
          '13 октября 2026 мы привели публичный рынок в порядок.',
          'Если у одного человека было несколько публичных приложений с тем же именем, адресом, загруженным значком или содержимым страницы, мы оставили только самое новое. Более ранние ушли с рынка. Ссылки на скачивание открываются, возвращать эти копии мы не будем.',
          'Значок, на 90% состоящий из одного цвета, включая почти фиолетовую плашку, использовать нельзя. Такие картинки сняты. Белый квадрат на карточке — пустое место под значок, а не белый значок, который мы нарисовали.',
          'Если приложение всё ещё в рынке, а место значка пустое, соберите его заново с настоящим рисунком до 20 октября 2026, 16:00 UTC. Если к этому времени значка нет или он снова однотонный, приложение уйдёт с рынка. Однотонный значок, найденный позже, получает те же семь дней с дня, когда мы его заметили.'
        ],
        es: [
          'El 13 de octubre de 2026 ordenamos el mercado público.',
          'Si una persona tenía varias apps públicas con el mismo nombre, la misma dirección, el mismo icono subido o el mismo contenido, dejamos solo la más nueva. Las anteriores salieron del mercado. El enlace de descarga sigue abriendo, y no vamos a devolver esas copias.',
          'Un icono que es un 90% de un solo color, incluido un bloque casi morado, no se puede usar. Quitamos esas imágenes. El cuadrado blanco de la ficha es el hueco vacío, no un icono blanco que hayamos pintado.',
          'Si tu app sigue en el mercado y el hueco está vacío, vuelve a generarla con un dibujo de verdad antes del 20 de octubre de 2026, 16:00 UTC. Si entonces sigue vacío o sigue siendo un color plano, la app sale del mercado. Un icono plano que encontremos más adelante tiene los mismos siete días desde el día en que lo veamos.'
        ],
        pt: [
          'Em 13 de outubro de 2026 arrumamos o mercado público.',
          'Quando a mesma pessoa tinha vários apps públicos com o mesmo nome, o mesmo endereço, o mesmo ícone enviado ou o mesmo conteúdo, ficou só o mais novo. Os anteriores saíram do mercado. O link de download continua abrindo, e essas cópias não voltam.',
          'Um ícone em que uma cor ocupa 90% da imagem não pode ser usado, inclusive um bloco quase roxo. Essas imagens foram retiradas. O quadrado branco no card é o espaço vazio, não um ícone branco que tenhamos desenhado.',
          'Se o seu app continua no mercado e o espaço do ícone está vazio, gere de novo com um desenho de verdade até 20 de outubro de 2026, 16:00 UTC. Se nessa hora ainda estiver vazio ou ainda for uma cor chapada, o app sai do mercado. Um ícone chapado encontrado depois ganha os mesmos sete dias a partir do dia em que o virmos.'
        ],
        fr: [
          'Le 13 octobre 2026, le marché public a été rangé.',
          'Quand une même personne avait plusieurs apps publiques avec le même nom, la même adresse, la même icône envoyée ou le même contenu, seule la plus récente est restée. Les plus anciennes ont quitté le marché. Le lien de téléchargement s’ouvre encore, et ces copies ne reviennent pas.',
          'Une icône dont 90 % est d’une seule couleur, y compris un aplat presque violet, ne peut pas servir. Ces images ont été retirées. Le carré blanc sur la fiche est l’emplacement vide, pas une icône blanche que nous aurions dessinée.',
          'Si votre app est encore au marché et que l’emplacement est vide, régénérez-la avec un vrai dessin avant le 20 octobre 2026, 16:00 UTC. S’il est encore vide ou encore d’une couleur unie à ce moment-là, l’app quitte le marché. Une icône unie trouvée plus tard a les mêmes sept jours à partir du jour où nous la voyons.'
        ],
        de: [
          'Am 13. Oktober 2026 haben wir den öffentlichen Markt aufgeräumt.',
          'Hatte dieselbe Person mehrere öffentliche Apps mit demselben Namen, derselben Adresse, demselben hochgeladenen Symbol oder demselben Inhalt, ist nur die neueste geblieben. Die älteren haben den Markt verlassen. Der Download-Link geht noch auf, und diese Kopien kommen nicht zurück.',
          'Ein Symbol, das zu 90 % aus einer Farbe besteht, auch ein fast lilafarbener Block, kann nicht verwendet werden. Diese Bilder sind weg. Das weiße Quadrat auf der Karte ist der leere Platz, kein weißes Symbol, das wir gezeichnet hätten.',
          'Wenn deine App noch im Markt steht und der Platz leer ist, erstelle sie bis zum 20. Oktober 2026, 16:00 UTC neu mit einem echten Bild. Ist er dann noch leer oder wieder einfarbig, verlässt die App den Markt. Ein später gefundenes flaches Symbol bekommt dieselben sieben Tage ab dem Tag, an dem wir es sehen.'
        ]
      }
    }
  ];

  function pick(map, lang) {
    if (!map) return null;
    if (map[lang]) return map[lang];
    if (map.en) return map.en;
    return map.zh || null;
  }

  function esc(text) {
    return String(text == null ? '' : text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function dateLabel(iso) {
    var day = String(iso || '').slice(0, 10);
    return day || '';
  }

  function render() {
    var root = document.getElementById('announcements');
    if (!root) return;
    var lang = (window.I18n && LANGS.indexOf(window.I18n.current) !== -1) ? window.I18n.current : 'en';
    var chrome = CHROME[lang] || CHROME.en;
    if (!NOTICES.length) {
      root.hidden = true;
      root.innerHTML = '';
      return;
    }
    var items = NOTICES.map(function (notice, index) {
      var title = pick(notice.title, lang) || notice.id;
      var paragraphs = pick(notice.paragraphs, lang) || [];
      var body = paragraphs.map(function (paragraph) {
        return '<p>' + esc(paragraph) + '</p>';
      }).join('');
      var open = index === 0 ? ' open' : '';
      return '' +
        '<li class="announce-item">' +
          '<time class="announce-date" datetime="' + esc(notice.publishedAt) + '">' + esc(dateLabel(notice.publishedAt)) + '</time>' +
          '<span class="announce-rail" aria-hidden="true"><span class="announce-dot"></span></span>' +
          '<details class="announce-entry"' + open + '>' +
            '<summary class="announce-title">' + esc(title) + '</summary>' +
            '<div class="announce-body">' + body + '</div>' +
          '</details>' +
        '</li>';
    }).join('');
    root.hidden = false;
    root.innerHTML =
      '<div class="announce-board">' +
        '<p class="announce-kicker">' + esc(chrome.kicker) + '</p>' +
        '<h2 id="announce-title" class="announce-heading">' + esc(chrome.heading) + '</h2>' +
        '<ol class="announce-timeline">' + items + '</ol>' +
      '</div>';
  }

  window.WTA_NOTICES = NOTICES;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', render);
  } else {
    render();
  }
  window.addEventListener('i18n:changed', render);
})();
