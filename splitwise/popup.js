document.addEventListener('DOMContentLoaded', async () => {
  await DB.open();
  const settings = await Auth.getSettings();
  const theme = settings.theme || 'light';
  document.documentElement.setAttribute('data-theme', theme);

  const setup = await Auth.isSetup();
  if (!setup) {
    App.navigate('setup');
  } else if (Auth.isLocked()) {
    App.navigate('lock');
  } else {
    Auth.startAutoLock(settings.autoLockMinutes || 5);
    App.navigate('dashboard');
  }

  // Reset auto-lock timer on any interaction
  document.addEventListener('click', () => Auth.resetTimer());
  document.addEventListener('keydown', () => Auth.resetTimer());
});
