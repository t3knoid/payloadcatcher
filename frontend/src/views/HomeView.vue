<script setup lang="ts">
import { onMounted } from 'vue';

import CallbackCard from '@/components/CallbackCard.vue';
import EventList from '@/components/EventList.vue';
import PayloadPanel from '@/components/PayloadPanel.vue';
import MainLayout from '@/layouts/MainLayout.vue';
import { useInboxStore } from '@/stores/inbox';

const store = useInboxStore();

onMounted(() => {
  store.bootstrapHome();
});
</script>

<template>
  <MainLayout :status-label="store.statusLabel">
    <CallbackCard
      :callback-url="store.callbackUrl"
      :viewer-url="store.viewerUrl"
      :copied="store.copied"
      :copying="store.loading"
      @copy="store.copyCallbackUrl"
    />

    <p v-if="store.error" class="error-banner">{{ store.error }}</p>

    <section class="workspace-grid">
      <EventList
        :events="store.events"
        :loading="store.loading"
        :loading-more="store.loadingMore"
        :selected-request-id="store.selectedRequestId"
        :search-value="store.search"
        :has-next-page="Boolean(store.inbox?.next_token)"
        @search="store.refreshSearch"
        @select="store.selectRequest"
        @next="store.loadNextPage"
      />
      <PayloadPanel :event="store.selectedEvent" />
    </section>
  </MainLayout>
</template>