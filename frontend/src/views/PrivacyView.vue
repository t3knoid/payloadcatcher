<script setup lang="ts">
import MainLayout from '@/layouts/MainLayout.vue';
</script>

<template>
  <MainLayout status-label="Notice">
    <section class="card privacy-page">
      <div class="privacy-page__copy">
        <p class="section-label">Operator Privacy Notes</p>
        <h2 class="privacy-page__title">Metadata collection stays limited and GPS remains opt-in.</h2>
        <p class="privacy-page__body">
          When an inbox is provisioned, PayloadCatcher records connection and browser context needed to operate the
          public capture URL safely. This includes source IP, browser and device hints, language, timezone, referer,
          and only the sanitized request headers allowed by the backend configuration.
        </p>
        <h3 class="privacy-page__subtitle">GPS data</h3>
        <p class="privacy-page__body">
          Precise GPS coordinates are collected only after an explicit user opt-in. If geolocation is unavailable,
          inbox provisioning continues without storing GPS values.
        </p>
        <h3 class="privacy-page__subtitle">Operator responsibilities</h3>
        <ul class="privacy-page__list">
          <li>Treat visit metadata as potentially regulated personal data.</li>
          <li>Configure trusted proxies correctly before relying on forwarded IP or locality headers.</li>
          <li>Document your retention and disclosure policies for captured metadata.</li>
        </ul>
        <div class="privacy-page__actions">
          <a class="callback-card__copy" href="/">Return to inbox provisioning</a>
        </div>
      </div>
    </section>
  </MainLayout>
</template>