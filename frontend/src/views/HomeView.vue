<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import CallbackCard from '@/components/CallbackCard.vue';
import EventList from '@/components/EventList.vue';
import PayloadPanel from '@/components/PayloadPanel.vue';
import MainLayout from '@/layouts/MainLayout.vue';
import { useInboxStore } from '@/stores/inbox';
import type { BootstrapRequest, VisitMetadataUpdateRequest } from '@/types/api';

const store = useInboxStore();
const PRIVACY_NOTICE_KEY = 'payloadcatcher_privacy_notice_ack';

const privacyAcknowledged = ref(false);
const gpsOptIn = ref(false);
const privacyMessage = ref<string | null>(null);
const privacyActionPending = ref(false);

const supportsPreciseLocation = computed(() => {
  return typeof navigator !== 'undefined' && 'geolocation' in navigator;
});

const resolveTimezone = () => {
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return timezone || undefined;
};

const requestPreciseLocation = () => {
  return new Promise<GeolocationPosition>((resolve, reject) => {
    if (!supportsPreciseLocation.value) {
      reject(new Error('Precise location is unavailable.'));
      return;
    }

    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: false,
      maximumAge: 300000,
      timeout: 4000,
    });
  });
};

const buildBootstrapRequest = async () => {
  const request: BootstrapRequest = {
    timezone: resolveTimezone(),
  };

  return request;
};

const buildVisitMetadataUpdate = async () => {
  const payload: VisitMetadataUpdateRequest = {
    gpsConsent: true,
  };

  if (!gpsOptIn.value) {
    return null;
  }

  try {
    const position = await requestPreciseLocation();
    payload.gpsLat = position.coords.latitude;
    payload.gpsLng = position.coords.longitude;
    privacyMessage.value = null;
  } catch {
    privacyMessage.value = 'Precise location was unavailable. Continuing with connection and browser metadata only.';
    return null;
  }

  return payload;
};

const runBootstrap = async () => {
  privacyActionPending.value = true;
  try {
    const bootstrapMetadata = await buildBootstrapRequest();
    const bootstrapResult = await store.bootstrapHome(bootstrapMetadata);
    if (!bootstrapResult) {
      return false;
    }

    const visitMetadataUpdate = await buildVisitMetadataUpdate();
    if (visitMetadataUpdate) {
      try {
        await store.updateVisitMetadata(visitMetadataUpdate);
      } catch {
        privacyMessage.value = 'Precise location could not be saved. Continuing with connection and browser metadata only.';
      }
    }
    return true;
  } finally {
    privacyActionPending.value = false;
  }
};

const acknowledgeAndStart = async () => {
  const bootstrapSucceeded = await runBootstrap();
  if (!bootstrapSucceeded) {
    return;
  }

  window.localStorage.setItem(PRIVACY_NOTICE_KEY, 'accepted');
  privacyAcknowledged.value = true;
};

onMounted(() => {
  privacyAcknowledged.value = window.localStorage.getItem(PRIVACY_NOTICE_KEY) === 'accepted';
  if (privacyAcknowledged.value) {
    void runBootstrap();
  }
});
</script>

<template>
  <MainLayout :status-label="store.statusLabel">
    <section v-if="!privacyAcknowledged" class="card privacy-card" data-testid="privacy-notice">
      <div class="privacy-card__copy">
        <p class="section-label">Privacy Notice</p>
        <h2 class="privacy-card__title">Review metadata collection before opening a public inbox.</h2>
        <p class="privacy-card__body">
          PayloadCatcher records connection and browser context such as source IP, browser and device hints,
          language, timezone, referer, and selected sanitized headers when an inbox is provisioned.
        </p>
        <p class="privacy-card__body">
          Precise GPS coordinates are collected only when you explicitly opt in below. Review the
          <a class="privacy-card__link" href="/privacy">operator privacy notes</a>
          before continuing.
        </p>
      </div>

      <label class="privacy-card__consent" for="gps-consent-toggle">
        <input id="gps-consent-toggle" v-model="gpsOptIn" type="checkbox" :disabled="privacyActionPending" />
        <span>
          Allow one-time precise GPS collection for this device.
          <small v-if="!supportsPreciseLocation"> This browser does not expose geolocation.</small>
        </span>
      </label>

      <p v-if="privacyMessage" class="privacy-card__message">{{ privacyMessage }}</p>

      <div class="privacy-card__actions">
        <button
          type="button"
          class="callback-card__copy"
          data-testid="privacy-start-button"
          :disabled="privacyActionPending"
          @click="acknowledgeAndStart"
        >
          {{ privacyActionPending ? 'Starting inbox...' : 'Review and start inbox' }}
        </button>
      </div>
    </section>

    <CallbackCard
      :callback-url="store.callbackUrl"
      :viewer-url="store.viewerUrl"
      :copied="store.copied"
      :copying="store.loading"
      @copy="store.copyCallbackUrl"
    />

    <p v-if="store.error" class="error-banner">{{ store.error }}</p>
  <p v-if="privacyMessage" class="privacy-info-banner">{{ privacyMessage }}</p>

    <section v-if="privacyAcknowledged" class="workspace-grid">
      <EventList
        :events="store.events"
        :loading="store.loading"
        :loading-more="store.loadingMore"
        :selected-request-id="store.selectedRequestId"
        :search-value="store.search"
        :current-page="store.currentPage"
        :has-next-page="store.hasNextPage"
        :has-previous-page="store.hasPreviousPage"
        @search="store.refreshSearch"
        @select="store.selectRequest"
        @next="store.loadNextPage"
        @previous="store.loadPreviousPage"
      />
      <PayloadPanel
        :detail="store.selectedEventDetail"
        :loading="store.detailLoading"
        :error="store.detailError"
        :copying="store.payloadCopying"
        :copied="store.payloadCopied"
        @copy="store.copyPayload"
      />
    </section>
  </MainLayout>
</template>