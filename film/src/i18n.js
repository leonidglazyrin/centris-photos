// Language for on-screen text: ?lang=fr renders the French version.
export const LANG = new URLSearchParams(globalThis.location?.search ?? '').get('lang') ?? 'en';

const FR = {
  // dialogue
  'Grandma always said the last post waits...': 'Grand-mère disait toujours que le dernier poteau attend...',
  '...for someone worth lighting it for.': "...quelqu'un pour qui ça vaut la peine de l'allumer.",
  "Hi! Is this... Willow Lake? It isn't on any map.": "Bonjour ! C'est bien... le Lac des Saules ? Il n'est sur aucune carte.",
  'Then your map is wrong.': 'Alors ta carte est fausse.',
  "I'm Rowan. I draw maps.": 'Moi, c\'est Rowan. Je dessine des cartes.',
  'Juno. I make lanterns.': 'Juno. Je fabrique des lanternes.',
  'Then maybe you can help me find my way.': "Alors tu pourras peut-être m'aider à trouver mon chemin.",
  'This is the grove. Every tree here has a name.': 'Voici le bosquet. Chaque arbre ici a un nom.',
  'Rivers, ridges, roads... I can map all of it.': 'Rivières, crêtes, chemins... je peux tout cartographier.',
  'Not all of it.': 'Pas tout.',
  'Mine looks like a potato.': 'La mienne ressemble à une patate.',
  "A glowing potato. It's perfect.": "Une patate lumineuse. Elle est parfaite.",
  "The map's almost finished.": 'La carte est presque finie.',
  '...And then you leave.': '...Et ensuite tu pars.',
  "Cartographers always leave. It's the job.": "Les cartographes partent toujours. C'est le métier.",
  "I'll come back.": 'Je reviendrai.',
  'Everyone says that.': 'Tout le monde dit ça.',
  'So you can find your way back.': 'Pour que tu retrouves ton chemin.',
  'I finished the map.': "J'ai fini la carte.",
  'Turns out every road on it leads here.': 'Il se trouve que tous ses chemins mènent ici.',
  'You followed the lantern.': 'Tu as suivi la lanterne.',
  'I followed you.': "C'est toi que j'ai suivie.",
  // supers, titles, credits
  'Willow Lake. Spring.': 'Lac des Saules. Printemps.',
  'Winter.': 'Hiver.',
  'Spring.': 'Printemps.',
  'THE LAST LANTERN': 'LA DERNIÈRE LANTERNE',
  'a love story in blocks': "une histoire d'amour en blocs",
  'starring': 'avec',
  'written & directed by': 'écrit et réalisé par',
  'every block placed with love': 'chaque bloc posé avec amour',
  // the hand-drawn map
  'Willow Lake': 'Lac des Saules',
  'Cherry Grove': 'Bosquet des cerisiers',
  'Our tree': 'Notre arbre',
  'HOME': 'CHEZ NOUS',
  'unexplored': 'inexploré',
};

export const tr = (s) => (LANG === 'fr' ? FR[s] ?? s : s);
